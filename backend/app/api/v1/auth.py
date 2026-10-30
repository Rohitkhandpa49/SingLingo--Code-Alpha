import hashlib
import logging
import secrets
from typing import Any
from datetime import datetime, timedelta, timezone

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.core.security import hash_password, verify_password
from app.database.repositories.users import UserRecord, UserRepository
from app.dependencies.auth import (
    ACCESS_TOKEN_COOKIE,
    get_current_user,
    get_user_from_access_token,
)
from app.dependencies.database import get_database
from app.schemas.auth import (
    AuthResponse,
    AccessibilityPreferences,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    UserResponse,
)
from app.services.auth import clear_session_cookie, set_session_cookie
from app.services.password_reset import (
    PasswordResetDeliveryError,
    send_password_reset_email,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)


def to_user_response(user: UserRecord) -> UserResponse:
    allowed_preferences = AccessibilityPreferences.model_fields
    return UserResponse(
        id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        created_at=user.created_at,
        preferred_language=user.preferred_language,
        preferred_sign_language=user.preferred_sign_language,
        accessibility_preferences={
            key: value
            for key, value in user.accessibility_preferences.items()
            if key in allowed_preferences
        },
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    repository = UserRepository(database)
    email = str(payload.email)
    if await repository.get_by_email(email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    password_hash = await anyio.to_thread.run_sync(
        hash_password,
        payload.password.get_secret_value(),
    )
    try:
        user = await repository.create(
            payload.full_name,
            email,
            password_hash,
        )
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None

    set_session_cookie(response, user, settings)
    return AuthResponse(user=to_user_response(user))


@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    repository = UserRepository(database)
    user = await repository.get_by_email(str(payload.email))
    password = payload.password.get_secret_value()
    if user is None:
        await anyio.to_thread.run_sync(hash_password, password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    password_matches = await anyio.to_thread.run_sync(
        verify_password,
        password,
        user.password_hash,
    )
    if not password_matches or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    set_session_cookie(response, user, settings)
    return AuthResponse(user=to_user_response(user))


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if token is None:
        authorization = request.headers.get("authorization", "")
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = credentials
    if token:
        try:
            user = await get_user_from_access_token(token, database, settings)
        except HTTPException as error:
            if error.status_code != status.HTTP_401_UNAUTHORIZED:
                raise
        else:
            await UserRepository(database).increment_session_version(user.id)
    clear_session_cookie(response, settings)
    return MessageResponse(message="Signed out")


@router.get("/me", response_model=AuthResponse)
async def get_session(user: UserRecord = Depends(get_current_user)) -> AuthResponse:
    return AuthResponse(user=to_user_response(user))


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit("3/hour")
async def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    if settings.smtp_host is None or settings.smtp_from_email is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email is not configured",
        )

    user = await UserRepository(database).get_by_email(str(payload.email))
    if user is None or not user.is_active:
        return MessageResponse(
            message="If the account exists, password reset instructions will be emailed."
        )

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )
    repository = UserRepository(database)
    if not await repository.save_password_reset_token(user.id, token_hash, expires_at):
        return MessageResponse(
            message="If the account exists, password reset instructions will be emailed."
        )
    try:
        await anyio.to_thread.run_sync(
            send_password_reset_email,
            user.email,
            token,
            settings,
        )
    except PasswordResetDeliveryError as error:
        await repository.clear_password_reset_token(token_hash)
        logger.error(
            "Password reset email delivery failed",
            extra={"error_type": error.__class__.__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email could not be sent",
        ) from None
    return MessageResponse(
        message="If the account exists, password reset instructions will be emailed."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
@limiter.limit("5/minute")
async def confirm_password_reset(
    request: Request,
    payload: PasswordResetConfirmRequest,
    response: Response,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    password_hash = await anyio.to_thread.run_sync(
        hash_password,
        payload.password.get_secret_value(),
    )
    user = await UserRepository(database).reset_password(
        token_hash,
        password_hash,
        datetime.now(timezone.utc),
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset link is invalid or expired",
        )
    clear_session_cookie(response, settings)
    return MessageResponse(message="Password updated. Please sign in.")

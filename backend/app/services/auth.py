from fastapi import Response

from app.core.config import Settings
from app.core.security import create_access_token
from app.dependencies.auth import ACCESS_TOKEN_COOKIE
from app.database.repositories.users import UserRecord


def set_session_cookie(response: Response, user: UserRecord, settings: Settings) -> None:
    token = create_access_token(user.id, settings, user.session_version)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=token,
        httponly=True,
        secure=settings.cookie_secure or settings.app_env == "production",
        samesite="lax",
        max_age=settings.jwt_access_token_expire_minutes * 60,
        path="/api/v1",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE,
        httponly=True,
        secure=settings.cookie_secure or settings.app_env == "production",
        samesite="lax",
        path="/api/v1",
    )

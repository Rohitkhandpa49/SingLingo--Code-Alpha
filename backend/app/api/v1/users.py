from typing import Any

import anyio
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pymongo.asynchronous.database import AsyncDatabase

from app.api.v1.auth import to_user_response
from app.core.config import Settings, get_settings
from app.core.security import verify_password
from app.database.repositories.users import UserRecord, UserRepository
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_database
from app.schemas.auth import (
    AccountDeletionRequest,
    MessageResponse,
    ProfileUpdateRequest,
    UserResponse,
)
from app.services.auth import clear_session_cookie

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_my_profile(user: UserRecord = Depends(get_current_user)) -> UserResponse:
    return to_user_response(user)


@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    payload: ProfileUpdateRequest,
    user: UserRecord = Depends(get_current_user),
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> UserResponse:
    updates = payload.model_dump(exclude_unset=True)
    if "accessibility_preferences" in updates:
        preferences = payload.accessibility_preferences
        if preferences is not None:
            updates.pop("accessibility_preferences")
            updates.update(
                {
                    f"accessibility_preferences.{key}": value
                    for key, value in preferences.model_dump(exclude_unset=True).items()
                }
            )
    updated_user = await UserRepository(database).update_profile(user.id, updates)
    if updated_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required",
        )
    return to_user_response(updated_user)


@router.delete("/me", response_model=MessageResponse)
async def delete_my_account(
    payload: AccountDeletionRequest,
    response: Response,
    user: UserRecord = Depends(get_current_user),
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    password_matches = await anyio.to_thread.run_sync(
        verify_password,
        payload.password.get_secret_value(),
        user.password_hash,
    )
    if not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password is incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await UserRepository(database).delete_account_data(user.id)
    clear_session_cookie(response, settings)
    return MessageResponse(message="Account and associated personal data deleted")

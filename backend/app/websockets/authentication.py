from typing import Any

from fastapi import HTTPException, WebSocket
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.database.repositories.users import UserRecord
from app.dependencies.auth import ACCESS_TOKEN_COOKIE, get_user_from_access_token


async def authenticate_websocket(
    websocket: WebSocket,
    database: AsyncDatabase[dict[str, Any]],
    settings: Settings,
) -> UserRecord:
    return await get_user_from_access_token(
        websocket.cookies.get(ACCESS_TOKEN_COOKIE),
        database,
        settings,
    )


def is_allowed_origin(websocket: WebSocket, settings: Settings) -> bool:
    origin = websocket.headers.get("origin")
    return (
        origin is not None
        and origin.rstrip("/") == str(settings.frontend_origin).rstrip("/")
    )

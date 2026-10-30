from typing import Any

from fastapi import APIRouter, WebSocket
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.services.gesture_classifier import GestureClassifier
from app.websockets.manager import ConnectionManager
from app.websockets.rate_limiter import UserMessageRateLimiter
from app.websockets.sign_socket import handle_sign_socket

router = APIRouter(tags=["real-time gesture inference"])


@router.websocket("/ws/gestures")
async def gesture_stream(websocket: WebSocket) -> None:
    settings: Settings = websocket.app.state.settings
    database: AsyncDatabase[dict[str, Any]] | None = getattr(
        websocket.app.state,
        "database",
        None,
    )
    classifier: GestureClassifier = websocket.app.state.gesture_classifier
    manager: ConnectionManager = websocket.app.state.websocket_manager
    rate_limiter: UserMessageRateLimiter = websocket.app.state.websocket_rate_limiter
    await handle_sign_socket(
        websocket,
        settings,
        database,
        classifier,
        manager,
        rate_limiter,
    )

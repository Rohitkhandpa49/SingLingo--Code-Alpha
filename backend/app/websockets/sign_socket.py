import logging
import secrets
from time import monotonic
from typing import Any

import anyio
from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.core.config import Settings
from app.database.documents import StoredDocumentError
from app.database.repositories.documents import SupportedSignsRepository
from app.isl import ISLSequenceInterpreter, ISLVocabulary
from app.services.gesture_classifier import GestureClassifier
from app.websockets.authentication import authenticate_websocket, is_allowed_origin
from app.websockets.backpressure import SlowWebSocketClient, send_json_bounded
from app.websockets.connection import WebSocketConnection
from app.websockets.heartbeat import HeartbeatMessage
from app.websockets.manager import ConnectionManager
from app.websockets.message_validation import (
    InvalidWebSocketMessage,
    decode_message,
    validate_sequence_order,
)
from app.websockets.rate_limiter import UserMessageRateLimiter

logger = logging.getLogger(__name__)


async def handle_sign_socket(
    websocket: WebSocket,
    settings: Settings,
    database: AsyncDatabase[dict[str, Any]] | None,
    classifier: GestureClassifier,
    manager: ConnectionManager,
    rate_limiter: UserMessageRateLimiter,
) -> None:
    origin_allowed = is_allowed_origin(websocket, settings)
    if not origin_allowed or database is None:
        await websocket.close(code=4403 if not origin_allowed else 1013)
        return

    await websocket.accept()
    try:
        user = await authenticate_websocket(websocket, database, settings)
    except HTTPException as error:
        if error.status_code != 401:
            raise
        await websocket.close(code=4401, reason="Authentication required")
        return
    except (PyMongoError, StoredDocumentError) as error:
        logger.error(
            "WebSocket authentication failed",
            extra={"error_type": error.__class__.__name__},
        )
        await websocket.close(code=1013, reason="Authentication service unavailable")
        return

    connection = await manager.register(str(user.id), websocket)
    if connection is None:
        await websocket.close(code=4429, reason="Connection limit reached")
        return

    try:
        await _run_connection(
            websocket,
            connection,
            settings,
            database,
            classifier,
            rate_limiter,
        )
    except WebSocketDisconnect:
        return
    finally:
        await manager.unregister(connection)


async def _run_connection(
    websocket: WebSocket,
    connection: WebSocketConnection,
    settings: Settings,
    database: AsyncDatabase[dict[str, Any]],
    classifier: GestureClassifier,
    rate_limiter: UserMessageRateLimiter,
) -> None:
    try:
        vocabulary_documents = await SupportedSignsRepository(
            database
        ).list_verified_for_version(settings.isl_vocabulary_version)
        vocabulary = ISLVocabulary(
            vocabulary_documents,
            version=settings.isl_vocabulary_version,
        )
    except (PyMongoError, StoredDocumentError, ValueError, RuntimeError) as error:
        logger.error(
            "ISL vocabulary could not be loaded",
            extra={"error_type": error.__class__.__name__},
        )
        await websocket.close(code=1013, reason="ISL vocabulary is unavailable")
        return
    interpreter = ISLSequenceInterpreter(
        vocabulary,
        confidence_threshold=settings.gesture_confidence_threshold,
    )
    heartbeat_nonce: str | None = None
    while True:
        if monotonic() - connection.authenticated_at >= settings.websocket_session_recheck_seconds:
            try:
                refreshed_user = await authenticate_websocket(
                    websocket,
                    database,
                    settings,
                )
            except HTTPException as error:
                if error.status_code != 401:
                    raise
                await websocket.close(code=4401, reason="Session expired")
                return
            except (PyMongoError, StoredDocumentError) as error:
                logger.error(
                    "WebSocket session validation failed",
                    extra={"error_type": error.__class__.__name__},
                )
                await websocket.close(code=1013, reason="Authentication service unavailable")
                return
            if str(refreshed_user.id) != connection.user_id:
                await websocket.close(code=4401, reason="Session changed")
                return
            connection.authenticated_at = monotonic()

        timeout = (
            settings.websocket_heartbeat_timeout_seconds
            if heartbeat_nonce is not None
            else settings.websocket_heartbeat_interval_seconds
        )
        with anyio.move_on_after(timeout) as receive_scope:
            event = await websocket.receive()

        if receive_scope.cancel_called:
            if heartbeat_nonce is not None:
                await websocket.close(code=4408, reason="Heartbeat timed out")
                return
            heartbeat_nonce = secrets.token_urlsafe(24)
            try:
                await send_json_bounded(
                    websocket,
                    {
                        "type": "system.heartbeat",
                        "action": "ping",
                        "nonce": heartbeat_nonce,
                    },
                    settings.websocket_send_timeout_seconds,
                )
            except SlowWebSocketClient:
                await websocket.close(code=1013, reason="Client is not receiving messages")
                return
            continue

        if event["type"] == "websocket.disconnect":
            return
        message = event.get("text")
        if not isinstance(message, str):
            await websocket.close(code=1003, reason="Only JSON text messages are accepted")
            return
        if len(message.encode("utf-8")) > settings.websocket_max_message_bytes:
            await websocket.close(code=1009, reason="Message is too large")
            return
        if not await rate_limiter.allow(connection.user_id):
            await websocket.close(code=4429, reason="Message rate limit exceeded")
            return

        try:
            decoded = decode_message(message)
        except InvalidWebSocketMessage:
            await _send_error(websocket, settings, "Invalid landmark sequence")
            continue

        if isinstance(decoded, HeartbeatMessage):
            if decoded.action == "pong":
                if heartbeat_nonce is not None and decoded.nonce != heartbeat_nonce:
                    await _send_error(websocket, settings, "Invalid heartbeat response")
                    continue
                heartbeat_nonce = None
                continue
            try:
                await send_json_bounded(
                    websocket,
                    {
                        "type": "system.heartbeat",
                        "action": "pong",
                        "nonce": decoded.nonce,
                    },
                    settings.websocket_send_timeout_seconds,
                )
            except SlowWebSocketClient:
                await websocket.close(code=1013, reason="Client is not receiving messages")
                return
            heartbeat_nonce = None
            continue

        heartbeat_nonce = None
        try:
            validate_sequence_order(
                decoded,
                connection,
                max_age_seconds=settings.websocket_sequence_max_age_seconds,
            )
        except InvalidWebSocketMessage:
            await _send_error(websocket, settings, "Invalid or out-of-order landmark sequence")
            continue

        try:
            prediction = await anyio.to_thread.run_sync(classifier.classify, decoded)
        except Exception as error:
            logger.error(
                "Gesture inference failed",
                extra={"error_type": error.__class__.__name__},
            )
            await _send_error(websocket, settings, "Gesture inference is temporarily unavailable")
            continue

        try:
            await send_json_bounded(
                websocket,
                {
                    "type": "gesture_result",
                    "sequence_id": str(decoded.sequence_id),
                    "status": prediction.status,
                    "label": prediction.label,
                    "confidence": prediction.confidence,
                    "model_version": prediction.model_version,
                    "translation": interpreter.interpret(
                        prediction,
                        session_id=decoded.session_id,
                        sequence_id=decoded.sequence_id,
                        language=decoded.output_language,
                    ).model_dump(mode="json"),
                },
                settings.websocket_send_timeout_seconds,
            )
        except SlowWebSocketClient:
            await websocket.close(code=1013, reason="Client is not receiving messages")
            return


async def _send_error(websocket: WebSocket, settings: Settings, detail: str) -> None:
    try:
        await send_json_bounded(
            websocket,
            {"type": "error", "detail": detail},
            settings.websocket_send_timeout_seconds,
        )
    except SlowWebSocketClient:
        await websocket.close(code=1013, reason="Client is not receiving messages")

import json
from datetime import datetime, timedelta, timezone
from json import JSONDecodeError
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.schemas.landmarks import LandmarkSequence
from app.websockets.connection import WebSocketConnection
from app.websockets.heartbeat import HeartbeatMessage


class InvalidWebSocketMessage(ValueError):
    pass


def decode_message(message: str) -> LandmarkSequence | HeartbeatMessage:
    try:
        payload: Any = json.loads(message)
    except JSONDecodeError as error:
        raise InvalidWebSocketMessage from error
    if not isinstance(payload, dict):
        raise InvalidWebSocketMessage
    try:
        if payload.get("type") == "system.heartbeat":
            return HeartbeatMessage.model_validate(payload)
        return LandmarkSequence.model_validate(payload)
    except ValidationError as error:
        raise InvalidWebSocketMessage from error


def validate_sequence_order(
    sequence: LandmarkSequence,
    connection: WebSocketConnection,
    now: datetime | None = None,
    max_age_seconds: int = 60,
) -> None:
    if sequence.sequence_id in connection.recent_sequence_id_set:
        raise InvalidWebSocketMessage

    if sequence.sequence is not None and sequence.timestamp is not None:
        if sequence.sequence <= connection.last_sequence:
            raise InvalidWebSocketMessage
        timestamp = sequence.timestamp.astimezone(timezone.utc)
        current_time = now or datetime.now(timezone.utc)
        if timestamp > current_time + timedelta(seconds=60):
            raise InvalidWebSocketMessage
        if timestamp < current_time - timedelta(seconds=max_age_seconds):
            raise InvalidWebSocketMessage
        if connection.last_timestamp is not None and timestamp <= connection.last_timestamp:
            raise InvalidWebSocketMessage
        connection.last_sequence = sequence.sequence
        connection.last_timestamp = timestamp

    connection.remember_sequence(sequence.sequence_id)

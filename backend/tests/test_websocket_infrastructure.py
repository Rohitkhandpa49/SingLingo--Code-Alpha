from datetime import datetime, timezone
from typing import Any
import anyio
import pytest

from app.schemas.landmarks import LandmarkSequence
from app.websockets.backpressure import SlowWebSocketClient, send_json_bounded
from app.websockets.connection import WebSocketConnection
from app.websockets.message_validation import (
    InvalidWebSocketMessage,
    decode_message,
    validate_sequence_order,
)
from app.websockets.rate_limiter import UserMessageRateLimiter


def sequence_payload(sequence_id: str = "00000000-0000-0000-0000-000000000001") -> dict[str, Any]:
    return {
        "type": "landmark_sequence",
        "sequence_id": sequence_id,
        "sample_rate_hz": 10,
        "sequence": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "frames": [{"hands": []} for _ in range(30)],
    }


def test_websocket_message_parser_accepts_landmarks_and_heartbeat() -> None:
    import json

    landmarks = decode_message(json.dumps(sequence_payload()))
    heartbeat = decode_message(
        json.dumps(
            {
                "type": "system.heartbeat",
                "action": "ping",
                "nonce": "n" * 24,
            }
        )
    )

    assert isinstance(landmarks, LandmarkSequence)
    assert heartbeat.type == "system.heartbeat"


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        '{"type":"landmark_sequence","raw_video":"forbidden"}',
        '{"type":"system.heartbeat","action":"ping","nonce":"short"}',
    ],
)
def test_websocket_message_parser_rejects_malformed_or_unsupported_data(
    payload: str,
) -> None:
    with pytest.raises(InvalidWebSocketMessage):
        decode_message(payload)


def test_sequence_validator_rejects_duplicate_sequence_ids_and_numbers() -> None:
    import json

    connection = WebSocketConnection(user_id="user", websocket=object())  # type: ignore[arg-type]
    sequence = decode_message(json.dumps(sequence_payload()))
    assert isinstance(sequence, LandmarkSequence)
    validate_sequence_order(sequence, connection)

    duplicate_id = decode_message(json.dumps(sequence_payload()))
    assert isinstance(duplicate_id, LandmarkSequence)
    with pytest.raises(InvalidWebSocketMessage):
        validate_sequence_order(duplicate_id, connection)


def test_rate_limit_is_shared_by_user_across_connections_and_expires() -> None:
    async def scenario() -> None:
        limiter = UserMessageRateLimiter(2, window_seconds=10)
        assert await limiter.allow("user-1", now=1)
        assert await limiter.allow("user-1", now=2)
        assert not await limiter.allow("user-1", now=3)
        assert await limiter.allow("user-1", now=12)

    anyio.run(scenario)


def test_slow_websocket_send_times_out() -> None:
    class SlowSocket:
        async def send_json(self, payload: dict[str, Any]) -> None:
            await anyio.sleep(0.1)

    async def scenario() -> None:
        with pytest.raises(SlowWebSocketClient):
            await send_json_bounded(SlowSocket(), {"type": "test"}, 0.001)  # type: ignore[arg-type]

    anyio.run(scenario)

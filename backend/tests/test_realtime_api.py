from datetime import datetime, timedelta, timezone
import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from conftest import FakeDatabase
from app.websockets.manager import ConnectionManager
from app.websockets.rate_limiter import UserMessageRateLimiter


ORIGIN_HEADER = {"origin": "http://localhost:3000"}


def register(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test User",
            "email": "streamer@example.com",
            "password": "a-secure-password",
        },
    )
    assert response.status_code == 201


def landmark_sequence() -> dict[str, object]:
    return {
        "type": "landmark_sequence",
        "sequence_id": "00000000-0000-0000-0000-000000000001",
        "sample_rate_hz": 10,
        "frames": [{"hands": []} for _ in range(30)],
    }


def test_authenticated_websocket_returns_unknown_without_a_model(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as websocket:
        websocket.send_json(landmark_sequence())
        response = websocket.receive_json()

    assert response["type"] == "gesture_result"
    assert response["sequence_id"] == "00000000-0000-0000-0000-000000000001"
    assert response["status"] == "model_unavailable"
    assert response["label"] is None
    assert response["confidence"] is None
    assert response["translation"]["status"] == "unsupported"
    assert response["translation"]["interpreted_text"] == ""


def test_websocket_rejects_raw_media_fields(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)
    payload = landmark_sequence()
    payload["raw_video"] = "not-accepted"

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as websocket:
        websocket.send_json(payload)
        response = websocket.receive_json()

    assert response == {"type": "error", "detail": "Invalid landmark sequence"}


def test_websocket_rejects_unsupported_output_language(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)
    payload = landmark_sequence()
    payload["output_language"] = "fr"

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as websocket:
        websocket.send_json(payload)
        response = websocket.receive_json()

    assert response == {"type": "error", "detail": "Invalid landmark sequence"}


def test_websocket_rejects_out_of_range_normalized_landmarks(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)
    payload = landmark_sequence()
    payload["frames"] = [
        {
            "hands": [
                {
                    "handedness": "Left",
                    "points": [{"x": 1.1, "y": 0.0, "z": 0.0} for _ in range(21)],
                }
            ]
        },
        *({"hands": []} for _ in range(29)),
    ]

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as websocket:
        websocket.send_json(payload)
        response = websocket.receive_json()

    assert response == {"type": "error", "detail": "Invalid landmark sequence"}


def test_websocket_rejects_binary_messages(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as websocket:
        websocket.send_bytes(b"raw video")
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_text()

    assert error.value.code == 1003


def test_websocket_requires_an_authenticated_session(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as websocket:
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_text()

    assert error.value.code == 4401


def test_websocket_heartbeat_round_trip_and_connection_cleanup(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)
    client.app.state.settings.websocket_heartbeat_interval_seconds = 0.01
    client.app.state.settings.websocket_heartbeat_timeout_seconds = 0.05

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as websocket:
        heartbeat = websocket.receive_json()
        assert heartbeat["type"] == "system.heartbeat"
        assert heartbeat["action"] == "ping"
        websocket.send_json(
            {
                "type": "system.heartbeat",
                "action": "pong",
                "nonce": heartbeat["nonce"],
            }
        )
        websocket.send_json(landmark_sequence())
        assert websocket.receive_json()["type"] == "gesture_result"

    assert client.app.state.websocket_manager.active_connection_count == 0


def test_websocket_closes_client_that_does_not_answer_heartbeat(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)
    client.app.state.settings.websocket_heartbeat_interval_seconds = 0.01
    client.app.state.settings.websocket_heartbeat_timeout_seconds = 0.02

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as websocket:
        assert websocket.receive_json()["action"] == "ping"
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_text()

    assert error.value.code == 4408


def test_websocket_revalidates_revoked_sessions(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = api_client
    register(client)
    client.app.state.settings.websocket_heartbeat_interval_seconds = 0.01
    client.app.state.settings.websocket_heartbeat_timeout_seconds = 0.05
    client.app.state.settings.websocket_session_recheck_seconds = 0.001

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as websocket:
        heartbeat = websocket.receive_json()
        database["users"].documents[0]["session_version"] += 1
        websocket.send_json(
            {
                "type": "system.heartbeat",
                "action": "pong",
                "nonce": heartbeat["nonce"],
            }
        )
        with pytest.raises(WebSocketDisconnect) as error:
            while True:
                next_message = websocket.receive_json()
                assert next_message["type"] == "system.heartbeat"
                websocket.send_json(
                    {
                        "type": "system.heartbeat",
                        "action": "pong",
                        "nonce": next_message["nonce"],
                    }
                )

    assert error.value.code == 4401


def test_websocket_rejects_replayed_or_out_of_order_sequences(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)
    now = datetime.now(timezone.utc)

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as websocket:
        first = landmark_sequence()
        first["sequence"] = 2
        first["timestamp"] = now.isoformat()
        websocket.send_json(first)
        assert websocket.receive_json()["type"] == "gesture_result"

        older = landmark_sequence()
        older["sequence_id"] = "00000000-0000-0000-0000-000000000002"
        older["sequence"] = 1
        older["timestamp"] = (now - timedelta(seconds=1)).isoformat()
        websocket.send_json(older)
        assert websocket.receive_json() == {
            "type": "error",
            "detail": "Invalid or out-of-order landmark sequence",
        }


def test_websocket_sanitizes_inference_failures(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)

    def fail_inference(_sequence: object) -> object:
        raise RuntimeError("internal model path and implementation details")

    client.app.state.gesture_classifier.classify = fail_inference
    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as websocket:
        websocket.send_json(landmark_sequence())
        assert websocket.receive_json() == {
            "type": "error",
            "detail": "Gesture inference is temporarily unavailable",
        }


def test_websocket_connection_limit_is_per_user(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)
    client.app.state.websocket_manager = ConnectionManager(max_connections_per_user=1)

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as first:
        assert client.app.state.websocket_manager.active_connection_count == 1
        with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as second:
            with pytest.raises(WebSocketDisconnect) as error:
                second.receive_text()
        assert error.value.code == 4429
        assert client.app.state.websocket_manager.active_connection_count == 1


def test_websocket_rate_limit_is_shared_across_reconnections(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)
    client.app.state.websocket_rate_limiter = UserMessageRateLimiter(1)

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as first:
        first.send_json(landmark_sequence())
        assert first.receive_json()["type"] == "gesture_result"

    second_sequence = landmark_sequence()
    second_sequence["sequence_id"] = "00000000-0000-0000-0000-000000000002"
    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as second:
        second.send_json(second_sequence)
        with pytest.raises(WebSocketDisconnect) as error:
            second.receive_text()

    assert error.value.code == 4429


def test_websocket_closes_oversized_payload(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)
    client.app.state.settings.websocket_max_message_bytes = 1024

    with client.websocket_connect("/api/v1/ws/gestures", headers=ORIGIN_HEADER) as websocket:
        websocket.send_text(" " * 1025)
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_text()

    assert error.value.code == 1009

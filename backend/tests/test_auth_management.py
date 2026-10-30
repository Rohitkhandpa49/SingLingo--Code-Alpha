import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from bson import ObjectId
from fastapi.testclient import TestClient

from conftest import FakeDatabase
from app.services.password_reset import PasswordResetDeliveryError


def register(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Asha Patel",
            "email": "asha@example.com",
            "password": "a-secure-password",
        },
    )
    assert response.status_code == 201


def test_profile_can_update_name_and_accessibility_preferences(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = client_and_database
    register(client)
    preferences = {
        "live_captions": False,
        "visual_alerts": True,
        "vibration_enabled": True,
        "reduced_motion": True,
        "theme": "dark",
        "camera_enabled": False,
    }

    response = client.patch(
        "/api/v1/users/me",
        json={
            "full_name": "Asha R.",
            "preferred_language": "hi",
            "preferred_sign_language": "ISL",
            "accessibility_preferences": preferences,
        },
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Asha R."
    assert response.json()["preferred_language"] == "hi"
    assert response.json()["accessibility_preferences"] == preferences
    stored = database["users"].documents[0]
    assert stored["accessibility_preferences"] == preferences
    assert stored["email"] == "asha@example.com"

    partial_response = client.patch(
        "/api/v1/users/me",
        json={"accessibility_preferences": {"reduced_motion": False}},
    )
    assert partial_response.status_code == 200
    assert partial_response.json()["accessibility_preferences"]["reduced_motion"] is False
    assert partial_response.json()["accessibility_preferences"]["live_captions"] is False


def test_profile_rejects_empty_or_invalid_updates(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = client_and_database
    register(client)

    assert client.patch("/api/v1/users/me", json={}).status_code == 422
    response = client.patch(
        "/api/v1/users/me",
        json={"accessibility_preferences": {"unknown_setting": True}},
    )
    assert response.status_code == 422
    assert client.patch(
        "/api/v1/users/me",
        json={"accessibility_preferences": {}},
    ).status_code == 422


def test_logout_revokes_the_previous_access_token(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = client_and_database
    register(client)
    token = client.cookies.get("signlingo_access")
    assert token is not None

    assert client.post("/api/v1/auth/logout").status_code == 200
    client.cookies.set("signlingo_access", token, path="/api/v1")

    assert client.get("/api/v1/auth/me").status_code == 401
    assert database["users"].documents[0]["session_version"] == 1


def test_password_reset_is_single_use_hashed_and_revokes_sessions(
    client_and_database: tuple[TestClient, FakeDatabase],
    monkeypatch: Any,
) -> None:
    client, database = client_and_database
    register(client)
    token = client.cookies.get("signlingo_access")
    sent_tokens: list[str] = []
    settings = client.app.state.settings
    settings.smtp_host = "smtp.example.test"
    settings.smtp_from_email = "noreply@example.test"

    def capture_email(email: str, raw_token: str, configured_settings: Any) -> None:
        assert email == "asha@example.com"
        assert configured_settings is settings
        sent_tokens.append(raw_token)

    monkeypatch.setattr("app.api.v1.auth.send_password_reset_email", capture_email)
    request_response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "ASHA@example.com"},
    )
    assert request_response.status_code == 202
    assert len(sent_tokens) == 1
    assert sent_tokens[0] not in request_response.text

    stored_user = database["users"].documents[0]
    assert stored_user["password_reset_token_hash"] == hashlib.sha256(
        sent_tokens[0].encode("utf-8")
    ).hexdigest()

    reset_payload = {
        "token": sent_tokens[0],
        "password": "a-new-secure-password",
        "password_confirmation": "a-new-secure-password",
    }
    reset_response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json=reset_payload,
    )
    assert reset_response.status_code == 200
    assert "password_reset_token_hash" not in stored_user
    assert stored_user["session_version"] == 1

    reuse_response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json=reset_payload,
    )
    assert reuse_response.status_code == 400
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "asha@example.com", "password": "a-secure-password"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "asha@example.com", "password": "a-new-secure-password"},
    ).status_code == 200
    if token is not None:
        client.cookies.set("signlingo_access", token, path="/api/v1")
        assert client.get("/api/v1/auth/me").status_code == 401


def test_password_reset_returns_generic_unknown_account_response(
    client_and_database: tuple[TestClient, FakeDatabase],
    monkeypatch: Any,
) -> None:
    client, _ = client_and_database
    settings = client.app.state.settings
    settings.smtp_host = "smtp.example.test"
    settings.smtp_from_email = "noreply@example.test"
    monkeypatch.setattr(
        "app.api.v1.auth.send_password_reset_email",
        lambda *_args: (_ for _ in ()).throw(AssertionError("unexpected email")),
    )

    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "unknown@example.com"},
    )

    assert response.status_code == 202
    assert response.json()["message"] == (
        "If the account exists, password reset instructions will be emailed."
    )


def test_password_reset_delivery_failure_clears_the_token(
    client_and_database: tuple[TestClient, FakeDatabase],
    monkeypatch: Any,
) -> None:
    client, database = client_and_database
    register(client)
    settings = client.app.state.settings
    settings.smtp_host = "smtp.example.test"
    settings.smtp_from_email = "noreply@example.test"

    def fail_delivery(*_args: Any) -> None:
        raise PasswordResetDeliveryError("mail service unavailable")

    monkeypatch.setattr("app.api.v1.auth.send_password_reset_email", fail_delivery)
    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "asha@example.com"},
    )

    assert response.status_code == 503
    assert "password_reset_token_hash" not in database["users"].documents[0]


def test_password_reset_rejects_expired_tokens(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = client_and_database
    register(client)
    token = "x" * 43
    database["users"].documents[0]["password_reset_token_hash"] = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()
    database["users"].documents[0]["password_reset_expires_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    )

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": token,
            "password": "a-new-secure-password",
            "password_confirmation": "a-new-secure-password",
        },
    )

    assert response.status_code == 400


def test_legacy_jwt_without_session_version_remains_valid(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = client_and_database
    register(client)
    user_id = database["users"].documents[0]["_id"]
    now = datetime.now(timezone.utc)
    settings = client.app.state.settings
    token = jwt.encode(
        {
            "sub": str(user_id),
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    client.cookies.clear()
    client.cookies.set("signlingo_access", token, path="/api/v1")

    assert client.get("/api/v1/auth/me").status_code == 200


def test_password_reset_is_explicitly_disabled_without_smtp(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = client_and_database
    register(client)

    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "asha@example.com"},
    )

    assert response.status_code == 503
    assert "password_reset_token_hash" not in database["users"].documents[0]


def test_registration_server_checks_password_confirmation(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client

    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Asha Patel",
            "email": "asha@example.com",
            "password": "a-secure-password",
            "password_confirmation": "a-different-password",
        },
    )

    assert response.status_code == 422


def test_account_deletion_removes_owned_data_and_preserves_other_participants(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = client_and_database
    register(client)
    user_id = database["users"].documents[0]["_id"]
    other_user_id = ObjectId()
    for collection_name in (
        "translation_history",
        "notifications",
        "audio_events",
        "feedback",
        "user_preferences",
    ):
        database[collection_name].documents.append({"user_id": user_id})
    database["conversations"].documents.extend(
        [
            {
                "participants": [user_id],
                "preferred_languages": {str(user_id): "hi"},
            },
            {
                "participants": [user_id, other_user_id],
                "preferred_languages": {
                    str(user_id): "hi",
                    str(other_user_id): "en",
                },
            },
            {"participants": []},
        ]
    )

    response = client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": "a-secure-password"},
    )

    assert response.status_code == 200
    assert database["users"].documents == []
    for collection_name in (
        "translation_history",
        "notifications",
        "audio_events",
        "feedback",
        "user_preferences",
    ):
        assert database[collection_name].documents == []
    assert database["conversations"].documents == [
        {
            "participants": [other_user_id],
            "preferred_languages": {str(other_user_id): "en"},
        },
        {"participants": []},
    ]
    assert client.get("/api/v1/auth/me").status_code == 401


def test_account_deletion_requires_the_current_password(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = client_and_database
    register(client)

    response = client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": "incorrect-password"},
    )

    assert response.status_code == 401
    assert len(database["users"].documents) == 1


def test_account_deletion_can_be_retried_after_a_database_failure(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = client_and_database
    register(client)
    database["notifications"].fail_operations = True

    failed_response = client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": "a-secure-password"},
    )

    assert failed_response.status_code == 503
    assert len(database["users"].documents) == 1
    database["notifications"].fail_operations = False
    retry_response = client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": "a-secure-password"},
    )
    assert retry_response.status_code == 200
    assert database["users"].documents == []


def test_cross_origin_state_change_is_rejected(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = client_and_database

    response = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403

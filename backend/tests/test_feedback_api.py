from datetime import datetime, timezone

from bson import ObjectId
from fastapi.testclient import TestClient

from conftest import FakeDatabase


def register(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Feedback User",
            "email": "feedback@example.com",
            "password": "a-secure-password",
        },
    )
    assert response.status_code == 201


def feedback_payload() -> dict[str, object]:
    return {
        "translation_id": "00000000-0000-0000-0000-000000000001",
        "session_id": "00000000-0000-0000-0000-000000000002",
        "feedback_type": "correction",
        "rating": 2,
        "correction": "User-provided correction for review",
        "sign_id": "user-supplied-label",
    }


def test_feedback_requires_authentication(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client

    response = client.post("/api/v1/feedback", json=feedback_payload())

    assert response.status_code == 401


def test_feedback_is_scoped_to_authenticated_user_and_pending_review(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = api_client
    register(client)
    user_id = database["users"].documents[0]["_id"]

    response = client.post("/api/v1/feedback", json=feedback_payload())

    assert response.status_code == 201
    assert response.json()["verification_status"] == "pending_review"
    stored = database["feedback"].documents[0]
    assert stored["user_id"] == user_id
    assert stored["session_id"] == feedback_payload()["session_id"]
    assert stored["verification_status"] == "pending_review"


def test_feedback_validates_corrections_and_unknown_sign_references(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)

    missing_correction = feedback_payload()
    missing_correction["correction"] = None
    response = client.post("/api/v1/feedback", json=missing_correction)
    assert response.status_code == 422

    missing_sign_id = feedback_payload()
    missing_sign_id["feedback_type"] = "unknown_sign"
    missing_sign_id["sign_id"] = None
    missing_sign_id["correction"] = None
    response = client.post("/api/v1/feedback", json=missing_sign_id)
    assert response.status_code == 422


def test_vocabulary_coverage_reports_unconfigured_empty_catalog(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)

    response = client.get("/api/v1/isl/vocabulary/coverage")

    assert response.status_code == 200
    assert response.json() == {
        "vocabulary_version": None,
        "verified_sign_count": 0,
        "verified_phrase_count": 0,
        "supported_languages": [],
        "sentence_grammar_available": False,
    }


def test_vocabulary_lookup_requires_verified_configured_record(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = api_client
    register(client)
    client.app.state.settings.isl_vocabulary_version = "fixture-v1"
    database["supported_signs"].documents.extend(
        [
            {
                "_id": ObjectId(),
                "sign_id": "verified-fixture",
                "sign_name": "Fixture record",
                "sign_category": "fixture",
                "language": "isl",
                "verification_status": "verified",
                "vocabulary_version": "fixture-v1",
                "translation_texts": {"en": "fixture-only text"},
                "compatible_model_versions": ["fixture-model"],
                "sequence_sign_ids": [],
                "created_at": datetime.now(timezone.utc),
            },
            {
                "_id": ObjectId(),
                "sign_id": "unverified-fixture",
                "sign_name": "Unverified fixture",
                "sign_category": "fixture",
                "language": "isl",
                "verification_status": "unverified",
                "vocabulary_version": "fixture-v1",
                "translation_texts": {"en": "must not appear"},
                "compatible_model_versions": ["fixture-model"],
                "sequence_sign_ids": [],
                "created_at": datetime.now(timezone.utc),
            },
        ]
    )

    verified = client.get("/api/v1/isl/vocabulary/verified-fixture")
    unverified = client.get("/api/v1/isl/vocabulary/unverified-fixture")

    assert verified.status_code == 200
    assert verified.json()["translations"] == {"en": "fixture-only text"}
    assert verified.json()["verification_status"] == "verified"
    assert unverified.status_code == 404

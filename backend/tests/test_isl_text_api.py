from datetime import datetime, timezone

from bson import ObjectId
from fastapi.testclient import TestClient

from app.database.documents import SupportedSignDocument
from conftest import FakeDatabase


def register(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Text Translation User",
            "email": "text-translation@example.com",
            "password": "a-secure-password",
        },
    )
    assert response.status_code == 201


def add_vocabulary(
    database: FakeDatabase,
    *,
    sign_id: str,
    translation: str,
    sequence_sign_ids: list[str] | None = None,
    verified: bool = True,
) -> None:
    document = SupportedSignDocument(
        sign_id=sign_id,
        sign_name=f"Fixture {sign_id}",
        sign_category="fixture",
        language="isl",
        verification_status="verified" if verified else "unverified",
        vocabulary_version="fixture-v1",
        translation_texts={"en": translation},
        compatible_model_versions=["fixture-model"],
        sequence_sign_ids=sequence_sign_ids or [],
        created_at=datetime.now(timezone.utc),
    ).model_dump(by_alias=True, exclude_none=True)
    document["_id"] = ObjectId()
    database["supported_signs"].documents.append(document)


def test_text_translation_requires_authentication(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client

    response = client.post(
        "/api/v1/isl/translate-text",
        json={"text": "hello", "language": "en"},
    )

    assert response.status_code == 401


def test_text_translation_returns_verified_sequence_and_unsupported_spans(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = api_client
    register(client)
    client.app.state.settings.isl_vocabulary_version = "fixture-v1"
    add_vocabulary(database, sign_id="hello", translation="hello")
    add_vocabulary(database, sign_id="morning", translation="morning")
    add_vocabulary(
        database,
        sign_id="phrase",
        translation="good morning",
        sequence_sign_ids=["hello", "morning"],
    )

    mapped = client.post(
        "/api/v1/isl/translate-text",
        json={"text": "GOOD morning", "language": "en"},
    )
    partial = client.post(
        "/api/v1/isl/translate-text",
        json={"text": "hello unknown", "language": "en"},
    )

    assert mapped.status_code == 200
    assert mapped.json()["status"] == "success"
    assert mapped.json()["translation_level"] == "phrase"
    assert [item["sign_id"] for item in mapped.json()["sequence"]] == ["hello", "morning"]
    assert mapped.json()["sequence"][0]["animation_asset"] is None
    assert partial.json()["status"] == "partial"
    assert partial.json()["unsupported_segments"][0]["text"] == "unknown"


def test_text_translation_rejects_invalid_input_and_unknown_language(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)

    invalid_language = client.post(
        "/api/v1/isl/translate-text",
        json={"text": "hello", "language": "fr"},
    )
    oversized = client.post(
        "/api/v1/isl/translate-text",
        json={"text": "x" * 5001, "language": "en"},
    )
    blank = client.post(
        "/api/v1/isl/translate-text",
        json={"text": "   ", "language": "en"},
    )

    assert invalid_language.status_code == 422
    assert oversized.status_code == 422
    assert blank.status_code == 422


def test_unconfigured_vocabulary_never_fabricates_a_sign_mapping(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = api_client
    register(client)
    add_vocabulary(database, sign_id="hello", translation="hello")

    response = client.post(
        "/api/v1/isl/translate-text",
        json={"text": "hello", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unsupported"
    assert response.json()["sequence"] == []

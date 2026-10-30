from fastapi.testclient import TestClient

from conftest import FakeDatabase


def register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test User",
            "email": email,
            "password": "a-secure-password"
        },
    )
    assert response.status_code == 201


def create_entry(
    client: TestClient,
    input_text: str,
    output_text: str = "I need help",
) -> dict[str, object]:
    return client.post(
        "/api/v1/history",
        json={
            "direction": "sign_to_speech",
            "source_language": "isl",
            "target_language": "en",
            "input_text": input_text,
            "output_text": output_text,
            "confidence": 0.92,
        },
    ).json()


def test_history_search_language_filter_and_delete(api_client: tuple[TestClient, FakeDatabase]) -> None:
    client, _ = api_client
    register(client, "asha@example.com")
    entry = create_entry(client, "water please")
    create_entry(client, "thank you", "Thanks")

    response = client.get(
        "/api/v1/history",
        params={"search": "water", "language": "en", "limit": 10},
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["id"] == entry["id"]
    assert response.json()["items"][0]["confidence"] == 0.92

    deleted = client.delete(f"/api/v1/history/{entry['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/v1/history").json()["items"][0]["input_text"] == "thank you"


def test_history_is_private_to_the_authenticated_user(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client, "first@example.com")
    entry = create_entry(client, "private phrase")

    client.cookies.clear()
    register(client, "second@example.com")

    response = client.get("/api/v1/history")
    delete_response = client.delete(f"/api/v1/history/{entry['id']}")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert delete_response.status_code == 404

    client.cookies.clear()
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "first@example.com", "password": "a-secure-password"},
    )
    assert login_response.status_code == 200
    assert client.get("/api/v1/history").json()["items"][0]["input_text"] == "private phrase"


def test_history_rejects_recording_payloads_and_invalid_date_ranges(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client, "asha@example.com")
    payload = {
        "direction": "sign_to_speech",
        "source_language": "isl",
        "target_language": "en",
        "input_text": "hello",
        "output_text": "hello",
        "raw_video": "not-accepted"
    }

    recording_response = client.post("/api/v1/history", json=payload)
    date_response = client.get(
        "/api/v1/history",
        params={
            "created_after": "2025-01-02T00:00:00Z",
            "created_before": "2025-01-01T00:00:00Z",
        },
    )

    assert recording_response.status_code == 422
    assert date_response.status_code == 422

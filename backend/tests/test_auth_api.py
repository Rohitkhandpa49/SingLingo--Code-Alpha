from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from conftest import FakeDatabase


@pytest.fixture
def client_and_database(api_client: tuple[TestClient, FakeDatabase]) -> Iterator[tuple[TestClient, FakeDatabase]]:
    yield api_client


def register(client: TestClient, email: str = "asha@example.com") -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Asha Patel",
            "email": email,
            "password": "a-secure-password"
        },
    )
    assert response.status_code == 201
    return response.json()


def test_registration_creates_a_protected_session_and_hides_password_hash(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = client_and_database
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Asha Patel",
            "email": "ASHA@example.com",
            "password": "a-secure-password"
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "asha@example.com"
    assert "password_hash" not in response.json()["user"]
    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1" in set_cookie
    assert client.get("/api/v1/auth/me").json()["user"]["full_name"] == "Asha Patel"
    assert database["users"].documents[0]["password_hash"].startswith("$argon2")
    assert database["users"].documents[0]["password_hash"] != "a-secure-password"


def test_duplicate_registration_is_rejected(client_and_database: tuple[TestClient, FakeDatabase]) -> None:
    client, _ = client_and_database
    register(client)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Asha Patel",
            "email": "ASHA@example.com",
            "password": "another-secure-password"
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "An account with this email already exists"


def test_login_rejects_wrong_password_and_logout_clears_session(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = client_and_database
    register(client)
    client.cookies.clear()

    invalid_response = client.post(
        "/api/v1/auth/login",
        json={"email": "asha@example.com", "password": "incorrect-password"},
    )
    assert invalid_response.status_code == 401
    assert invalid_response.json()["detail"] == "Email or password is incorrect"

    valid_response = client.post(
        "/api/v1/auth/login",
        json={"email": "asha@example.com", "password": "a-secure-password"},
    )
    assert valid_response.status_code == 200
    assert client.get("/api/v1/users/me").json()["email"] == "asha@example.com"

    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_unauthenticated_profile_is_rejected(api_client: tuple[TestClient, FakeDatabase]) -> None:
    client, _ = api_client
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_profile_reads_preserve_unrecognized_legacy_user_fields(
    client_and_database: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = client_and_database
    register(client)
    legacy_value = {"migration_note": "keep"}
    database["users"].documents[0]["legacy_profile_data"] = legacy_value

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert "legacy_profile_data" not in response.json()["user"]
    assert database["users"].documents[0]["legacy_profile_data"] == legacy_value

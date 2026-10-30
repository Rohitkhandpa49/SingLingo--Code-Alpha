from fastapi.testclient import TestClient

from conftest import FakeDatabase


def test_health_reports_database_readiness(api_client: tuple[TestClient, FakeDatabase]) -> None:
    client, _ = api_client
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_liveness_does_not_depend_on_mongodb(api_client: tuple[TestClient, FakeDatabase]) -> None:
    client, database = api_client
    database.fail_commands = True

    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "not_checked"}


def test_readiness_returns_safe_service_unavailable_on_database_failure(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = api_client
    database.fail_commands = True

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}


def test_database_errors_from_api_operations_are_sanitized(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = api_client
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Asha Patel",
            "email": "asha@example.com",
            "password": "a-secure-password",
        },
    )
    assert registration.status_code == 201
    database["users"].fail_operations = True

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database service is temporarily unavailable"}


def test_invalid_stored_user_data_returns_sanitized_server_error(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, database = api_client
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Asha Patel",
            "email": "asha@example.com",
            "password": "a-secure-password",
        },
    )
    assert response.status_code == 201
    database["users"].documents[0]["full_name"] = ""

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 500
    assert response.json() == {"detail": "Stored data failed validation"}

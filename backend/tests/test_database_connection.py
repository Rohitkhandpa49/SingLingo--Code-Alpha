from typing import Any

from app.core.config import Settings
from app.database import connection


def test_mongo_client_receives_configured_pool_and_timeout_options(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_client(uri: str, **options: Any) -> object:
        captured["uri"] = uri
        captured.update(options)
        return object()

    monkeypatch.setattr(connection, "AsyncMongoClient", fake_client)
    settings = Settings(
        app_env="test",
        mongodb_uri="mongodb://localhost:27017/signlingo_test",
        mongodb_database="signlingo_test",
        mongodb_max_pool_size=40,
        mongodb_min_pool_size=2,
        mongodb_max_idle_time_ms=60_000,
        mongodb_connect_timeout_ms=5_000,
        mongodb_server_selection_timeout_ms=7_000,
        mongodb_wait_queue_timeout_ms=3_000,
        jwt_secret="test-only-secret-that-is-at-least-32-bytes",
        frontend_origin="http://localhost:3000",
    )

    connection.create_mongo_client(settings)

    assert captured == {
        "uri": "mongodb://localhost:27017/signlingo_test",
        "appname": "SignLingo API",
        "maxPoolSize": 40,
        "minPoolSize": 2,
        "maxIdleTimeMS": 60_000,
        "connectTimeoutMS": 5_000,
        "serverSelectionTimeoutMS": 7_000,
        "waitQueueTimeoutMS": 3_000,
    }

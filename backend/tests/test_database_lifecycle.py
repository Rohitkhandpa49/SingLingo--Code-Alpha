import pytest
from fastapi.testclient import TestClient
from pymongo.errors import PyMongoError

from app.core.config import Settings
from app.main import create_app
from conftest import FakeDatabase


class FakeMongoClient:
    def __init__(self, database: FakeDatabase) -> None:
        self.database = database
        self.closed = False

    def get_database(self, name: str) -> FakeDatabase:
        assert name == "signlingo_test"
        return self.database

    async def close(self) -> None:
        self.closed = True


def make_settings() -> Settings:
    return Settings(
        app_env="development",
        mongodb_uri="mongodb://localhost:27017/signlingo_test",
        mongodb_database="signlingo_test",
        jwt_secret="test-only-secret-that-is-at-least-32-bytes",
        frontend_origin="http://localhost:3000",
    )


def test_lifespan_initializes_database_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = FakeDatabase()
    mongo_client = FakeMongoClient(database)

    def create_client(settings: Settings) -> FakeMongoClient:
        assert settings.mongodb_database == "signlingo_test"
        return mongo_client

    monkeypatch.setattr("app.main.create_mongo_client", create_client)
    app = create_app(make_settings())

    with TestClient(app):
        assert app.state.database is database
        assert len(database.collections) == 9

    assert mongo_client.closed


def test_lifespan_closes_client_when_database_startup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = FakeDatabase()
    database.fail_commands = True
    mongo_client = FakeMongoClient(database)
    monkeypatch.setattr(
        "app.main.create_mongo_client",
        lambda settings: mongo_client,
    )
    app = create_app(make_settings())

    with pytest.raises(PyMongoError):
        with TestClient(app):
            pass

    assert mongo_client.closed

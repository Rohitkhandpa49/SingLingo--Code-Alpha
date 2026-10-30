import pytest
from pydantic import ValidationError

from app.core.config import Settings


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "mongodb_uri": "mongodb://user:database-password@localhost:27017/signlingo_test",
        "mongodb_database": "signlingo_test",
        "jwt_secret": "test-only-secret-that-is-at-least-32-bytes",
        "frontend_origin": "http://localhost:3000",
    }
    return Settings(**(values | overrides))


def test_mongodb_uri_is_secret_and_pool_defaults_match_driver_defaults() -> None:
    settings = make_settings()

    assert "database-password" not in repr(settings)
    assert settings.mongodb_max_pool_size == 100
    assert settings.mongodb_min_pool_size == 0
    assert settings.mongodb_max_idle_time_ms is None
    assert settings.mongodb_wait_queue_timeout_ms is None


def test_mongodb_pool_rejects_minimum_above_maximum() -> None:
    with pytest.raises(ValidationError, match="MONGODB_MIN_POOL_SIZE"):
        make_settings(mongodb_max_pool_size=10, mongodb_min_pool_size=11)


def test_mongodb_uri_scheme_is_validated_without_revealing_credentials() -> None:
    with pytest.raises(ValidationError, match="MONGODB_URI"):
        make_settings(mongodb_uri="https://user:database-password@localhost")

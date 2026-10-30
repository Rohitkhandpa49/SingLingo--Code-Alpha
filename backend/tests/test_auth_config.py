import pytest
from pydantic import ValidationError

from app.core.config import Settings


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "mongodb_uri": "mongodb://localhost:27017/signlingo_test",
        "mongodb_database": "signlingo_test",
        "jwt_secret": "test-only-secret-that-is-at-least-32-bytes",
        "frontend_origin": "http://localhost:3000",
    }
    return Settings(**(values | overrides))


def test_smtp_requires_host_and_sender_together() -> None:
    with pytest.raises(ValidationError, match="SMTP_HOST and SMTP_FROM_EMAIL"):
        settings(smtp_host="smtp.example.test")


def test_smtp_authentication_requires_both_credentials() -> None:
    with pytest.raises(ValidationError, match="SMTP_USERNAME and SMTP_PASSWORD"):
        settings(
            smtp_host="smtp.example.test",
            smtp_from_email="noreply@example.com",
            smtp_username="signlingo",
        )


def test_production_requires_https_frontend_and_secure_cookie() -> None:
    with pytest.raises(ValidationError, match="FRONTEND_ORIGIN must use HTTPS"):
        settings(
            app_env="production",
            cookie_secure=True,
            frontend_origin="http://signlingo.example",
        )


def test_production_rejects_plaintext_smtp() -> None:
    with pytest.raises(ValidationError, match="SMTP_STARTTLS must be true"):
        settings(
            app_env="production",
            cookie_secure=True,
            frontend_origin="https://signlingo.example",
            smtp_host="smtp.example.test",
            smtp_from_email="noreply@example.com",
            smtp_starttls=False,
        )

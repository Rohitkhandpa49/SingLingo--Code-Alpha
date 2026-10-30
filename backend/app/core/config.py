from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, EmailStr, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    mongodb_uri: SecretStr = Field(min_length=1)
    mongodb_database: str = Field(default="signlingo", min_length=1)
    mongodb_max_pool_size: int = Field(default=100, ge=1, le=1000)
    mongodb_min_pool_size: int = Field(default=0, ge=0, le=1000)
    mongodb_max_idle_time_ms: int | None = Field(default=None, gt=0)
    mongodb_connect_timeout_ms: int = Field(default=20_000, gt=0)
    mongodb_server_selection_timeout_ms: int = Field(default=30_000, gt=0)
    mongodb_wait_queue_timeout_ms: int | None = Field(default=None, gt=0)
    history_retention_days: int | None = Field(default=None, ge=1, le=36500)
    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, gt=0, le=1440)
    password_reset_token_expire_minutes: int = Field(default=30, gt=0, le=120)
    smtp_host: str | None = Field(default=None, min_length=1)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: EmailStr | None = None
    smtp_starttls: bool = True
    smtp_timeout_seconds: int = Field(default=10, gt=0, le=60)
    frontend_origin: AnyHttpUrl = "http://localhost:3000"
    cookie_secure: bool = False
    backend_host: str = "0.0.0.0"
    backend_port: int = Field(default=8000, ge=1, le=65535)
    gesture_model_path: Path | None = None
    gesture_labels_path: Path | None = None
    gesture_confidence_threshold: float = Field(default=0.75, ge=0, le=1)
    isl_vocabulary_version: str | None = Field(default=None, min_length=1, max_length=64)
    whisper_model: Literal["tiny", "base", "small"] | None = None
    whisper_device: Literal["auto", "cpu", "cuda"] = "cpu"
    whisper_download_root: Path = Path("ai-engine/models/whisper")
    speech_max_audio_bytes: int = Field(default=4_000_000, ge=1024, le=20_000_000)
    speech_max_duration_seconds: int = Field(default=60, ge=1, le=300)
    websocket_max_message_bytes: int = Field(default=100_000, ge=1024, le=1_000_000)
    websocket_heartbeat_interval_seconds: float = Field(default=20, gt=0, le=300)
    websocket_heartbeat_timeout_seconds: float = Field(default=45, gt=0, le=600)
    websocket_rate_limit_per_minute: int = Field(default=120, ge=1, le=10_000)
    websocket_max_connections_per_user: int = Field(default=3, ge=1, le=100)
    websocket_send_timeout_seconds: float = Field(default=5, gt=0, le=60)
    websocket_sequence_max_age_seconds: int = Field(default=60, gt=0, le=3600)
    websocket_session_recheck_seconds: int = Field(default=60, gt=0, le=3600)
    websocket_shutdown_timeout_seconds: int = Field(default=10, gt=0, le=120)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("mongodb_uri")
    @classmethod
    def validate_mongodb_uri(cls, value: SecretStr) -> SecretStr:
        uri = value.get_secret_value()
        if not uri.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("MONGODB_URI must use mongodb:// or mongodb+srv://")
        return value

    @field_validator("smtp_host", "smtp_username")
    @classmethod
    def normalize_optional_smtp_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("isl_vocabulary_version", mode="before")
    @classmethod
    def normalize_vocabulary_version(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("whisper_model", mode="before")
    @classmethod
    def normalize_whisper_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        if self.mongodb_min_pool_size > self.mongodb_max_pool_size:
            raise ValueError("MONGODB_MIN_POOL_SIZE must not exceed MONGODB_MAX_POOL_SIZE")
        smtp_configured = self.smtp_host is not None or self.smtp_from_email is not None
        if smtp_configured and (self.smtp_host is None or self.smtp_from_email is None):
            raise ValueError("SMTP_HOST and SMTP_FROM_EMAIL must be configured together")
        if (self.smtp_username is None) != (self.smtp_password is None):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")
        secret = self.jwt_secret.get_secret_value()
        if len(secret.encode("utf-8")) < 32 or secret.startswith("replace_"):
            raise ValueError("JWT_SECRET must be replaced with at least 32 random bytes")
        if self.app_env == "production" and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        frontend_url = urlsplit(str(self.frontend_origin))
        if (
            frontend_url.path not in ("", "/")
            or frontend_url.query
            or frontend_url.fragment
            or frontend_url.username
            or frontend_url.password
        ):
            raise ValueError("FRONTEND_ORIGIN must contain only an origin")
        if self.app_env == "production":
            if frontend_url.scheme != "https":
                raise ValueError("FRONTEND_ORIGIN must use HTTPS in production")
            if self.smtp_host is not None and not self.smtp_starttls:
                raise ValueError("SMTP_STARTTLS must be true in production")
        if self.websocket_heartbeat_interval_seconds >= self.websocket_heartbeat_timeout_seconds:
            raise ValueError(
                "WEBSOCKET_HEARTBEAT_INTERVAL_SECONDS must be less than "
                "WEBSOCKET_HEARTBEAT_TIMEOUT_SECONDS"
            )
        if (self.gesture_model_path is None) != (self.gesture_labels_path is None):
            raise ValueError("GESTURE_MODEL_PATH and GESTURE_LABELS_PATH must be set together")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

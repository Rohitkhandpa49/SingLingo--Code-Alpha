from datetime import datetime

from typing import Literal

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator

from app.schemas.common import APIModel


class AccessibilityPreferences(APIModel):
    live_captions: bool = True
    visual_alerts: bool = True
    vibration_enabled: bool = False
    reduced_motion: bool = False
    theme: Literal["light", "dark", "system"] = "system"
    camera_enabled: bool = True


class AccessibilityPreferencesUpdate(APIModel):
    live_captions: bool | None = None
    visual_alerts: bool | None = None
    vibration_enabled: bool | None = None
    reduced_motion: bool | None = None
    theme: Literal["light", "dark", "system"] | None = None
    camera_enabled: bool | None = None

    @model_validator(mode="after")
    def require_preference_values(self) -> "AccessibilityPreferencesUpdate":
        if not self.model_fields_set or any(
            getattr(self, field_name) is None for field_name in self.model_fields_set
        ):
            raise ValueError("Provide at least one non-null accessibility preference")
        return self


class RegisterRequest(APIModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: SecretStr = Field(min_length=8, max_length=128)
    password_confirmation: SecretStr | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_password_confirmation(self) -> "RegisterRequest":
        if (
            self.password_confirmation is not None
            and self.password.get_secret_value()
            != self.password_confirmation.get_secret_value()
        ):
            raise ValueError("Passwords do not match")
        return self

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class LoginRequest(APIModel):
    email: EmailStr
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserResponse(APIModel):
    id: str
    full_name: str
    email: EmailStr
    created_at: datetime
    preferred_language: Literal["en", "hi"] | None = None
    preferred_sign_language: str | None = None
    accessibility_preferences: AccessibilityPreferences = Field(
        default_factory=AccessibilityPreferences
    )


class AuthResponse(APIModel):
    user: UserResponse


class MessageResponse(APIModel):
    message: str


class ProfileUpdateRequest(APIModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    preferred_language: Literal["en", "hi"] | None = None
    preferred_sign_language: str | None = Field(default=None, max_length=32)
    accessibility_preferences: AccessibilityPreferencesUpdate | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("preferred_sign_language", mode="before")
    @classmethod
    def normalize_sign_language(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_profile_field(self) -> "ProfileUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one profile field must be provided")
        if "full_name" in self.model_fields_set and self.full_name is None:
            raise ValueError("Full name cannot be cleared")
        if self.preferred_sign_language == "":
            raise ValueError("Preferred sign language must not be empty")
        if (
            "accessibility_preferences" in self.model_fields_set
            and self.accessibility_preferences is None
        ):
            raise ValueError("Accessibility preferences cannot be cleared")
        if (
            self.accessibility_preferences is not None
            and not self.accessibility_preferences.model_fields_set
        ):
            raise ValueError("At least one accessibility preference must be provided")
        return self


class AccountDeletionRequest(APIModel):
    password: SecretStr = Field(min_length=8, max_length=128)


class PasswordResetRequest(APIModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class PasswordResetConfirmRequest(APIModel):
    token: str = Field(min_length=32, max_length=256)
    password: SecretStr = Field(min_length=8, max_length=128)
    password_confirmation: SecretStr = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_password_confirmation(self) -> "PasswordResetConfirmRequest":
        if self.password.get_secret_value() != self.password_confirmation.get_secret_value():
            raise ValueError("Passwords do not match")
        return self

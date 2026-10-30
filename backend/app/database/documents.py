from datetime import datetime
from typing import Any, Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


class MongoDocument(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        extra="forbid",
    )

    id: ObjectId | None = Field(default=None, alias="_id")


class UserDocument(MongoDocument):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        extra="ignore",
    )

    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password_hash: str = Field(min_length=1, max_length=512)
    is_active: bool = True
    account_status: Literal["active", "suspended", "deleted"] | None = "active"
    session_version: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime | None = None
    profile_image: str | None = None
    preferred_language: Literal["en", "hi"] | None = None
    preferred_sign_language: str | None = Field(default=None, max_length=32)
    accessibility_preferences: dict[str, Any] = Field(default_factory=dict)
    password_reset_token_hash: str | None = Field(default=None, min_length=64, max_length=64)
    password_reset_expires_at: datetime | None = None


class HistoryDocument(MongoDocument):
    user_id: ObjectId
    direction: Literal["sign_to_speech", "speech_to_sign"]
    source_language: Literal["isl", "hi", "en"]
    target_language: Literal["isl", "hi", "en"]
    input_text: str = Field(min_length=1, max_length=5000)
    output_text: str = Field(min_length=1, max_length=5000)
    confidence: FiniteFloat | None = Field(default=None, ge=0, le=1)
    created_at: datetime
    conversation_id: str | None = None


class SupportedSignDocument(MongoDocument):
    sign_id: str = Field(min_length=1, max_length=100)
    sign_name: str = Field(min_length=1, max_length=200)
    sign_category: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    language: str = Field(min_length=1, max_length=32)
    hand_configuration: str | None = Field(default=None, max_length=1000)
    movement_description: str | None = Field(default=None, max_length=1000)
    hand_orientation: str | None = Field(default=None, max_length=1000)
    dominant_hand: str | None = Field(default=None, max_length=100)
    facial_expression: str | None = Field(default=None, max_length=1000)
    body_posture: str | None = Field(default=None, max_length=1000)
    animation_asset: str | None = Field(default=None, max_length=500)
    synonyms: list[str] = Field(default_factory=list, max_length=50)
    dataset_reference: str | None = Field(default=None, max_length=500)
    verification_status: Literal["unverified", "verified", "rejected"] = "unverified"
    vocabulary_version: str | None = Field(default=None, min_length=1, max_length=64)
    translation_texts: dict[Literal["en", "hi"], str] = Field(default_factory=dict)
    compatible_model_versions: list[str] = Field(default_factory=list, max_length=50)
    sequence_sign_ids: list[str] = Field(default_factory=list, max_length=32)
    created_at: datetime
    updated_at: datetime | None = None


class ConversationDocument(MongoDocument):
    conversation_id: str = Field(min_length=1, max_length=128)
    participants: list[ObjectId] = Field(min_length=1, max_length=2)
    conversation_status: Literal["active", "ended"] = "active"
    preferred_languages: dict[str, str] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None


class NotificationDocument(MongoDocument):
    user_id: ObjectId
    notification_type: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    priority: Literal["info", "important", "warning", "critical"] = "info"
    read_status: bool = False
    created_at: datetime


class AudioEventDocument(MongoDocument):
    user_id: ObjectId
    event_type: str = Field(min_length=1, max_length=100)
    detected_label: str = Field(min_length=1, max_length=200)
    confidence: FiniteFloat = Field(ge=0, le=1)
    severity: Literal["info", "important", "warning", "critical"]
    created_at: datetime


class FeedbackDocument(MongoDocument):
    user_id: ObjectId
    translation_id: str = Field(min_length=1, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    sign_id: str | None = Field(default=None, max_length=100)
    rating: int = Field(ge=1, le=5)
    correction: str | None = Field(default=None, max_length=5000)
    feedback_type: str = Field(min_length=1, max_length=100)
    verification_status: Literal["pending_review", "reviewed", "rejected"] = "pending_review"
    created_at: datetime


class ModelVersionDocument(MongoDocument):
    model_name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    architecture: str = Field(min_length=1, max_length=200)
    dataset_reference: str | None = Field(default=None, max_length=500)
    evaluation_metrics: dict[str, FiniteFloat] = Field(default_factory=dict)
    deployment_status: Literal["staged", "active", "retired"] = "staged"
    created_at: datetime


class UserPreferenceDocument(MongoDocument):
    user_id: ObjectId
    theme: Literal["light", "dark", "system"] = "system"
    language: Literal["en", "hi"] = "en"
    voice_settings: dict[str, Any] = Field(default_factory=dict)
    visual_alert_settings: dict[str, Any] = Field(default_factory=dict)
    vibration_enabled: bool = False
    caption_enabled: bool = True
    privacy_settings: dict[str, Any] = Field(default_factory=dict)


class StoredDocumentError(RuntimeError):
    def __init__(self, collection_name: str) -> None:
        super().__init__(f"Stored document in {collection_name!r} failed validation")
        self.collection_name = collection_name

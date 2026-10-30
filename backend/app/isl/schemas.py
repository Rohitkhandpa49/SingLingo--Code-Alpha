from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, FiniteFloat, model_validator

from app.schemas.common import APIModel

TranslationStatus = Literal[
    "success",
    "partial",
    "unknown_gesture",
    "low_confidence",
    "unsupported",
    "processing_error",
]
TranslationLevel = Literal[
    "single_sign",
    "fingerspelling",
    "number",
    "phrase",
    "sentence",
    "partial",
]


class RecognizedSign(APIModel):
    sign_id: str = Field(min_length=1, max_length=100)
    sign_name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    confidence: FiniteFloat = Field(ge=0, le=1)
    translation: str | None = Field(default=None, max_length=1000)
    hand_configuration: str | None = Field(default=None, max_length=1000)
    hand_movement: str | None = Field(default=None, max_length=1000)
    hand_orientation: str | None = Field(default=None, max_length=1000)
    dominant_hand: str | None = Field(default=None, max_length=100)
    facial_expression: str | None = Field(default=None, max_length=1000)
    body_position: str | None = Field(default=None, max_length=1000)


class UnsupportedSegment(APIModel):
    sign_id: str | None = Field(default=None, max_length=100)
    reason: str = Field(min_length=1, max_length=200)


class ISLTranslationResponse(APIModel):
    type: Literal["isl_translation"] = "isl_translation"
    translation_id: UUID
    status: TranslationStatus
    session_id: UUID | None = None
    sequence_id: UUID
    recognized_signs: list[RecognizedSign] = Field(max_length=32)
    interpreted_text: str = Field(default="", max_length=5000)
    language: Literal["en", "hi"] = "en"
    confidence: FiniteFloat | None = Field(default=None, ge=0, le=1)
    translation_level: TranslationLevel
    unsupported_segments: list[UnsupportedSegment] = Field(max_length=64)
    model_version: str | None = Field(default=None, max_length=100)
    vocabulary_version: str | None = Field(default=None, max_length=64)
    timestamp: datetime


class ISLVocabularyResponse(APIModel):
    sign_id: str
    sign_name: str
    category: str
    language: Literal["isl"] = "isl"
    translations: dict[Literal["en", "hi"], str]
    vocabulary_version: str
    compatible_model_versions: list[str]
    hand_configuration: str | None = None
    hand_movement: str | None = None
    hand_orientation: str | None = None
    dominant_hand: str | None = None
    facial_expression: str | None = None
    body_position: str | None = None
    dataset_reference: str | None = None
    verification_status: Literal["verified"] = "verified"


class ISLVocabularyCoverageResponse(APIModel):
    vocabulary_version: str | None
    verified_sign_count: int = Field(ge=0)
    verified_phrase_count: int = Field(ge=0)
    supported_languages: list[Literal["en", "hi"]]
    sentence_grammar_available: bool


class ISLTextTranslationRequest(APIModel):
    text: str = Field(min_length=1, max_length=5000)
    language: Literal["auto", "en", "hi"] = "auto"

    @model_validator(mode="after")
    def reject_blank_text(self) -> "ISLTextTranslationRequest":
        if not self.text.strip():
            raise ValueError("Text cannot be blank")
        return self


class ISLTextSequenceItem(APIModel):
    sign_id: str = Field(min_length=1, max_length=100)
    sign_name: str = Field(min_length=1, max_length=200)
    matched_text: str = Field(min_length=1, max_length=5000)
    animation_asset: str | None = Field(default=None, max_length=500)
    animation_clip: str | None = Field(default=None, max_length=100)


class ISLTextUnsupportedSegment(APIModel):
    start_index: int = Field(ge=0)
    end_index: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=5000)
    reason: Literal[
        "language_not_detected",
        "mixed_script_requires_language_selection",
        "no_word_tokens",
        "no_verified_mapping",
        "ambiguous_verified_mapping",
        "sentence_grammar_unavailable",
        "input_token_limit_exceeded",
        "sequence_limit_exceeded",
    ]


class ISLTextTranslationResponse(APIModel):
    type: Literal["isl_text_translation"] = "isl_text_translation"
    translation_id: UUID
    status: Literal["success", "partial", "unsupported"]
    source_text: str = Field(max_length=5000)
    normalized_text: str = Field(max_length=5000)
    language: Literal["en", "hi"] | None = None
    sequence: list[ISLTextSequenceItem] = Field(max_length=24)
    unsupported_segments: list[ISLTextUnsupportedSegment] = Field(max_length=64)
    translation_level: Literal["single_sign", "phrase", "partial"]
    vocabulary_version: str | None = Field(default=None, max_length=64)
    sentence_grammar_available: bool = False
    timestamp: datetime


class FeedbackCreateRequest(APIModel):
    translation_id: UUID
    session_id: UUID
    feedback_type: Literal["correction", "unknown_sign", "usefulness"]
    rating: int = Field(ge=1, le=5)
    correction: str | None = Field(default=None, min_length=1, max_length=5000)
    sign_id: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_request(self) -> "FeedbackCreateRequest":
        if self.feedback_type == "correction" and self.correction is None:
            raise ValueError("A correction is required for correction feedback")
        if self.correction is not None and not self.correction.strip():
            raise ValueError("A correction cannot be blank")
        if self.feedback_type == "unknown_sign" and self.sign_id is None:
            raise ValueError("A sign ID is required for unknown-sign feedback")
        if self.sign_id is not None and not self.sign_id.strip():
            raise ValueError("A sign ID cannot be blank")
        return self


class FeedbackResponse(APIModel):
    id: str
    verification_status: Literal["pending_review"]
    created_at: datetime

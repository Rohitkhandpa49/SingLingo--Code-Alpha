from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, FiniteFloat

from app.schemas.common import APIModel


class SpeechSegment(APIModel):
    start: FiniteFloat = Field(ge=0)
    end: FiniteFloat = Field(gt=0)
    text: str = Field(min_length=1, max_length=1000)


class SpeechTranscriptionResponse(APIModel):
    transcription_id: UUID
    session_id: UUID
    status: Literal["final"] = "final"
    original_text: str = Field(min_length=1, max_length=10_000)
    normalized_text: str = Field(min_length=1, max_length=10_000)
    language: Literal["en", "hi"]
    language_detection: Literal["selected", "whisper"]
    segments: list[SpeechSegment] = Field(max_length=500)
    model_name: str = Field(min_length=1, max_length=64)
    method: Literal["chunked"] = "chunked"
    timestamp: datetime

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

Direction = Literal["sign_to_speech", "speech_to_sign"]
LanguageCode = Literal["isl", "hi", "en"]


class HistoryCreateRequest(APIModel):
    direction: Direction
    source_language: LanguageCode
    target_language: LanguageCode
    input_text: str = Field(min_length=1, max_length=5000)
    output_text: str = Field(min_length=1, max_length=5000)
    confidence: float | None = Field(default=None, ge=0, le=1)


class HistoryResponse(APIModel):
    id: str
    direction: Direction
    source_language: LanguageCode
    target_language: LanguageCode
    input_text: str
    output_text: str
    confidence: float | None
    created_at: datetime


class HistoryListResponse(APIModel):
    items: list[HistoryResponse]
    limit: int
    skip: int

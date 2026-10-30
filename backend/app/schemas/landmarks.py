from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import APIModel


class LandmarkPoint(APIModel):
    x: float = Field(ge=-1, le=1, allow_inf_nan=False)
    y: float = Field(ge=-1, le=1, allow_inf_nan=False)
    z: float = Field(ge=-1, le=1, allow_inf_nan=False)


class HandLandmarks(APIModel):
    handedness: Literal["Left", "Right"]
    points: list[LandmarkPoint] = Field(min_length=21, max_length=21)
    wrist: LandmarkPoint | None = None
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)


class LandmarkFrame(APIModel):
    hands: list[HandLandmarks] = Field(max_length=2)
    hands_detected: int | None = Field(default=None, ge=0, le=2, strict=True)

    @model_validator(mode="after")
    def validate_hands(self) -> "LandmarkFrame":
        handedness = [hand.handedness for hand in self.hands]
        if len(handedness) != len(set(handedness)):
            raise ValueError("A frame cannot contain two hands with the same handedness")
        if self.hands_detected is not None and self.hands_detected != len(self.hands):
            raise ValueError("hands_detected must match the number of hand landmarks")
        return self


class LandmarkSequence(APIModel):
    type: Literal["landmark_sequence"]
    sequence_id: UUID
    sample_rate_hz: Literal[10]
    frames: list[LandmarkFrame] = Field(min_length=30, max_length=30)
    output_language: Literal["en", "hi"] = "en"
    schema_version: Literal["1.0"] = "1.0"
    session_id: UUID | None = None
    frame_width: int | None = Field(default=None, gt=0, le=16384)
    frame_height: int | None = Field(default=None, gt=0, le=16384)
    sequence: int | None = Field(default=None, strict=True, gt=0)
    timestamp: datetime | None = None

    @model_validator(mode="after")
    def validate_ordering_metadata(self) -> "LandmarkSequence":
        if (self.sequence is None) != (self.timestamp is None):
            raise ValueError("Sequence number and timestamp must be supplied together")
        if self.timestamp is not None and self.timestamp.tzinfo is None:
            raise ValueError("Timestamp must include a timezone")
        if (self.frame_width is None) != (self.frame_height is None):
            raise ValueError("Frame width and height must be supplied together")
        return self

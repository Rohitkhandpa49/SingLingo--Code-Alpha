from io import BytesIO
import wave
from uuid import UUID

import numpy as np
import pytest

from app.core.config import Settings
from app.services.speech.audio_preprocessor import TARGET_SAMPLE_RATE
from app.services.speech.service import (
    SpeechRecognitionService,
    SpeechServiceBusy,
    UnsupportedSpeechLanguage,
)
from app.services.speech.whisper_provider import SpeechProviderError


def pcm_wav(duration_seconds: float = 1) -> bytes:
    output = BytesIO()
    samples = np.full(
        int(duration_seconds * TARGET_SAMPLE_RATE),
        5000,
        dtype="<i2",
    )
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(TARGET_SAMPLE_RATE)
        wav.writeframes(samples.tobytes())
    return output.getvalue()


def make_settings() -> Settings:
    return Settings(
        app_env="test",
        mongodb_uri="mongodb://localhost:27017/signlingo_test",
        mongodb_database="signlingo_test",
        jwt_secret="test-only-secret-that-is-at-least-32-bytes",
        frontend_origin="http://localhost:3000",
        whisper_model="tiny",
    )


class FixtureProvider:
    model_name = "tiny"

    def __init__(self) -> None:
        self.calls: list[str | None] = []

    def transcribe(
        self,
        audio: np.ndarray,
        *,
        language: str | None,
    ) -> dict[str, object]:
        self.calls.append(language)
        chunk_texts = ["hello there", "there friend"]
        return {
            "text": chunk_texts[min(len(self.calls) - 1, 1)],
            "language": "en",
            "segments": [{"start": 0.1, "end": 0.8, "text": "spoken words"}],
        }


def test_transcribes_selected_language_and_returns_bounded_segments() -> None:
    provider = FixtureProvider()
    service = SpeechRecognitionService(make_settings(), provider)
    session_id = UUID("00000000-0000-0000-0000-000000000001")

    result = service.transcribe(
        pcm_wav(),
        content_type="audio/wav",
        language="hi",
        session_id=session_id,
    )

    assert provider.calls == ["hi"]
    assert result.normalized_text == "hello there"
    assert result.language == "hi"
    assert result.language_detection == "selected"
    assert result.session_id == session_id
    assert result.segments[0].start == pytest.approx(0.1)


def test_auto_detection_and_overlapping_chunk_text_are_processed() -> None:
    provider = FixtureProvider()
    service = SpeechRecognitionService(make_settings(), provider)

    result = service.transcribe(
        pcm_wav(31),
        content_type="audio/wav",
        language="auto",
        session_id=None,
    )

    assert provider.calls == [None, None]
    assert result.normalized_text == "hello there friend"
    assert result.language == "en"
    assert result.language_detection == "whisper"
    assert len(result.segments) == 2
    assert result.segments[1].start > result.segments[0].start


def test_rejects_unsupported_language_and_empty_transcript() -> None:
    service = SpeechRecognitionService(make_settings(), FixtureProvider())
    with pytest.raises(UnsupportedSpeechLanguage):
        service.transcribe(
            pcm_wav(),
            content_type="audio/wav",
            language="fr",
            session_id=None,
        )

    class EmptyProvider(FixtureProvider):
        def transcribe(
            self,
            audio: np.ndarray,
            *,
            language: str | None,
        ) -> dict[str, object]:
            return {"text": "  ", "language": "en"}

    with pytest.raises(SpeechProviderError, match="empty transcript"):
        SpeechRecognitionService(make_settings(), EmptyProvider()).transcribe(
            pcm_wav(),
            content_type="audio/wav",
            language="auto",
            session_id=None,
        )


def test_returns_busy_when_single_inference_slot_is_occupied() -> None:
    service = SpeechRecognitionService(make_settings(), FixtureProvider())
    assert service._inference_slot.acquire(blocking=False)
    try:
        with pytest.raises(SpeechServiceBusy):
            service.transcribe(
                pcm_wav(),
                content_type="audio/wav",
                language="en",
                session_id=None,
            )
    finally:
        service._inference_slot.release()

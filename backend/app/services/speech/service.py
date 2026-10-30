from collections.abc import Callable
from datetime import datetime, timezone
from threading import BoundedSemaphore
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

import numpy as np
from numpy.typing import NDArray

from app.core.config import Settings
from app.services.speech.audio_preprocessor import AudioPreprocessor
from app.services.speech.schemas import SpeechSegment, SpeechTranscriptionResponse
from app.services.speech.transcript_processor import (
    merge_overlapping_transcripts,
    normalize_transcript,
)
from app.services.speech.whisper_provider import (
    SpeechProviderError,
    SpeechProviderUnavailable,
    WhisperProvider,
)

SUPPORTED_LANGUAGES = {"en", "hi"}


class SpeechProvider(Protocol):
    model_name: str | None

    def transcribe(
        self,
        audio: NDArray[np.float32],
        *,
        language: str | None,
    ) -> dict[str, Any]: ...


class SpeechServiceBusy(RuntimeError):
    pass


class UnsupportedSpeechLanguage(ValueError):
    pass


class SpeechRecognitionService:
    def __init__(
        self,
        settings: Settings,
        provider: SpeechProvider | None = None,
        *,
        preprocessor_factory: Callable[..., AudioPreprocessor] = AudioPreprocessor,
    ) -> None:
        self._settings = settings
        self._provider = provider or WhisperProvider(
            model_name=settings.whisper_model,
            device=settings.whisper_device,
            download_root=settings.whisper_download_root,
        )
        self._preprocessor = preprocessor_factory(
            max_bytes=settings.speech_max_audio_bytes,
            max_duration_seconds=settings.speech_max_duration_seconds,
        )
        self._inference_slot = BoundedSemaphore(1)

    def transcribe(
        self,
        audio: bytes,
        *,
        content_type: str,
        language: str,
        session_id: UUID | None,
    ) -> SpeechTranscriptionResponse:
        if language not in {"auto", *SUPPORTED_LANGUAGES}:
            raise UnsupportedSpeechLanguage("Select auto, English, or Hindi")
        if not self._inference_slot.acquire(blocking=False):
            raise SpeechServiceBusy("Speech recognition is busy")
        try:
            samples = self._preprocessor.decode_wav(audio, content_type)
            chunks = self._preprocessor.chunks(samples)
            transcripts: list[str] = []
            segments: list[SpeechSegment] = []
            detected_languages: list[str] = []
            for chunk in chunks:
                result = self._provider.transcribe(
                    chunk.samples,
                    language=None if language == "auto" else language,
                )
                chunk_text = result.get("text")
                detected_language = result.get("language")
                if not isinstance(chunk_text, str):
                    raise SpeechProviderError("Whisper returned invalid transcript text")
                if isinstance(detected_language, str):
                    detected_languages.append(detected_language)
                transcripts.append(normalize_transcript(chunk_text))
                segments.extend(self._parse_segments(result.get("segments"), chunk.start_seconds))

            transcript = ""
            for chunk_text in transcripts:
                transcript = merge_overlapping_transcripts(transcript, chunk_text)
            normalized_text = normalize_transcript(transcript)
            if not normalized_text:
                raise SpeechProviderError("Whisper returned an empty transcript")

            if language == "auto":
                supported_detections = [
                    detected for detected in detected_languages if detected in SUPPORTED_LANGUAGES
                ]
                if not supported_detections:
                    raise UnsupportedSpeechLanguage(
                        "Whisper could not reliably identify Hindi or English"
                    )
                detected_language = max(
                    set(supported_detections),
                    key=supported_detections.count,
                )
                language_detection: Literal["selected", "whisper"] = "whisper"
            else:
                detected_language = language
                language_detection = "selected"

            return SpeechTranscriptionResponse(
                transcription_id=uuid4(),
                session_id=session_id or uuid4(),
                original_text=transcript,
                normalized_text=normalized_text,
                language=detected_language,
                language_detection=language_detection,
                segments=segments[:500],
                model_name=self._provider.model_name or "unconfigured",
                timestamp=datetime.now(timezone.utc),
            )
        finally:
            self._inference_slot.release()

    @staticmethod
    def _parse_segments(
        raw_segments: Any,
        offset_seconds: float,
    ) -> list[SpeechSegment]:
        if not isinstance(raw_segments, list):
            return []
        parsed: list[SpeechSegment] = []
        for segment in raw_segments:
            if not isinstance(segment, dict):
                continue
            text = segment.get("text")
            start = segment.get("start")
            end = segment.get("end")
            if (
                not isinstance(text, str)
                or not text.strip()
                or not isinstance(start, (int, float))
                or not isinstance(end, (int, float))
                or not np.isfinite(start)
                or not np.isfinite(end)
                or start < 0
                or end <= start
            ):
                continue
            parsed.append(
                SpeechSegment(
                    start=offset_seconds + float(start),
                    end=offset_seconds + float(end),
                    text=normalize_transcript(text),
                )
            )
        return parsed

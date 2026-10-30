from io import BytesIO
import wave
from uuid import UUID

import numpy as np
from fastapi.testclient import TestClient

from app.services.speech.schemas import SpeechTranscriptionResponse
from app.services.speech.whisper_provider import SpeechProviderUnavailable
from conftest import FakeDatabase


def pcm_wav() -> bytes:
    output = BytesIO()
    samples = np.full(16_000, 5000, dtype="<i2")
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(samples.tobytes())
    return output.getvalue()


def register(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Speech User",
            "email": "speech@example.com",
            "password": "a-secure-password",
        },
    )
    assert response.status_code == 201


class FixtureSpeechService:
    def __init__(self) -> None:
        self.audio: bytes | None = None
        self.language: str | None = None
        self.session_id: UUID | None = None

    def transcribe(
        self,
        audio: bytes,
        *,
        content_type: str,
        language: str,
        session_id: UUID | None,
    ) -> SpeechTranscriptionResponse:
        self.audio = audio
        self.language = language
        self.session_id = session_id
        return SpeechTranscriptionResponse(
            transcription_id=UUID("00000000-0000-0000-0000-000000000002"),
            session_id=session_id or UUID("00000000-0000-0000-0000-000000000003"),
            original_text="hello",
            normalized_text="hello",
            language="en",
            language_detection="selected",
            segments=[],
            model_name="fixture",
            timestamp="2026-10-30T00:00:00Z",
        )


def test_transcription_route_requires_authentication(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client

    response = client.post(
        "/api/v1/speech/transcribe",
        files={"audio": ("speech.wav", pcm_wav(), "audio/wav")},
        data={"language": "en"},
    )

    assert response.status_code == 401


def test_transcription_route_forwards_audio_and_returns_contract(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)
    service = FixtureSpeechService()
    client.app.state.speech_service = service
    session_id = "00000000-0000-0000-0000-000000000001"

    response = client.post(
        "/api/v1/speech/transcribe",
        files={"audio": ("speech.wav", pcm_wav(), "audio/wav")},
        data={"language": "hi", "session_id": session_id},
    )

    assert response.status_code == 200
    assert response.json()["normalized_text"] == "hello"
    assert service.audio == pcm_wav()
    assert service.language == "hi"
    assert str(service.session_id) == session_id


def test_transcription_route_sanitizes_provider_failures(
    api_client: tuple[TestClient, FakeDatabase],
) -> None:
    client, _ = api_client
    register(client)

    class UnavailableService:
        def transcribe(self, *args: object, **kwargs: object) -> None:
            raise SpeechProviderUnavailable("private provider details")

    client.app.state.speech_service = UnavailableService()
    response = client.post(
        "/api/v1/speech/transcribe",
        files={"audio": ("speech.wav", pcm_wav(), "audio/wav")},
        data={"language": "en"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Speech recognition is not configured or could not start"
    assert "private provider details" not in response.text

from io import BytesIO
import wave

import numpy as np
import pytest

from app.services.speech.audio_preprocessor import (
    AudioPreprocessor,
    AudioValidationError,
    TARGET_SAMPLE_RATE,
)


def pcm_wav(
    *,
    duration_seconds: float = 1,
    sample_rate: int = 16_000,
    amplitude: int = 5000,
    channels: int = 1,
) -> bytes:
    sample_count = int(duration_seconds * sample_rate)
    samples = np.full((sample_count, channels), amplitude, dtype="<i2")
    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())
    return output.getvalue()


def preprocessor(
    *,
    max_bytes: int = 4_000_000,
    max_duration_seconds: int = 60,
) -> AudioPreprocessor:
    return AudioPreprocessor(
        max_bytes=max_bytes,
        max_duration_seconds=max_duration_seconds,
    )


def test_decodes_stereo_pcm_and_resamples_to_16_khz() -> None:
    decoded = preprocessor().decode_wav(
        pcm_wav(duration_seconds=1, sample_rate=48_000, channels=2),
        "audio/wav",
    )

    assert decoded.dtype == np.float32
    assert decoded.size == TARGET_SAMPLE_RATE
    assert np.max(np.abs(decoded)) == pytest.approx(0.95)


@pytest.mark.parametrize(
    ("audio", "content_type", "message"),
    [
        (b"", "audio/wav", "empty"),
        (b"not a wav file", "audio/wav", "valid PCM WAV"),
        (pcm_wav(), "audio/webm", "PCM WAV"),
        (pcm_wav(amplitude=0), "audio/wav", "no detectable"),
        (pcm_wav(duration_seconds=2), "audio/wav", "duration limit"),
    ],
    ids=["empty", "corrupt", "unsupported-content-type", "silent", "over-duration"],
)
def test_rejects_invalid_silent_or_oversized_duration_audio(
    audio: bytes,
    content_type: str,
    message: str,
) -> None:
    processor = preprocessor(max_duration_seconds=1)
    with pytest.raises(AudioValidationError, match=message):
        processor.decode_wav(audio, content_type)


def test_rejects_audio_above_configured_byte_limit() -> None:
    with pytest.raises(AudioValidationError, match="size limit"):
        preprocessor(max_bytes=100).decode_wav(pcm_wav(), "audio/wav")


def test_chunks_long_recordings_with_one_second_overlap() -> None:
    samples = np.ones(31 * TARGET_SAMPLE_RATE, dtype=np.float32)

    chunks = AudioPreprocessor.chunks(samples)

    assert [chunk.start_seconds for chunk in chunks] == [0, 29]
    assert [chunk.samples.size for chunk in chunks] == [
        30 * TARGET_SAMPLE_RATE,
        2 * TARGET_SAMPLE_RATE,
    ]

from dataclasses import dataclass
from io import BytesIO
import wave

import numpy as np
from numpy.typing import NDArray

TARGET_SAMPLE_RATE = 16_000
MIN_SAMPLE_RATE = 8_000
MAX_SAMPLE_RATE = 48_000
CHUNK_SECONDS = 30
CHUNK_OVERLAP_SECONDS = 1


class AudioValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AudioChunk:
    start_seconds: float
    samples: NDArray[np.float32]


class AudioPreprocessor:
    def __init__(
        self,
        *,
        max_bytes: int,
        max_duration_seconds: int,
    ) -> None:
        self._max_bytes = max_bytes
        self._max_duration_seconds = max_duration_seconds

    def decode_wav(self, audio: bytes, content_type: str) -> NDArray[np.float32]:
        if content_type.lower().split(";", maxsplit=1)[0].strip() not in {
            "audio/wav",
            "audio/wave",
            "audio/x-wav",
        }:
            raise AudioValidationError("Upload a PCM WAV recording")
        if not audio or len(audio) > self._max_bytes:
            raise AudioValidationError("Audio is empty or exceeds the configured size limit")

        try:
            with wave.open(BytesIO(audio), "rb") as wav:
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                sample_rate = wav.getframerate()
                frame_count = wav.getnframes()
                if (
                    wav.getcomptype() != "NONE"
                    or channels not in {1, 2}
                    or sample_width != 2
                    or not MIN_SAMPLE_RATE <= sample_rate <= MAX_SAMPLE_RATE
                    or frame_count <= 0
                ):
                    raise AudioValidationError("WAV must be uncompressed 16-bit mono or stereo PCM")
                duration = frame_count / sample_rate
                if duration > self._max_duration_seconds:
                    raise AudioValidationError("Audio exceeds the configured duration limit")
                if duration < 0.1:
                    raise AudioValidationError("Audio recording is too short")
                frames = wav.readframes(frame_count)
        except AudioValidationError:
            raise
        except (wave.Error, EOFError, ValueError) as error:
            raise AudioValidationError("Audio is not a valid PCM WAV file") from error

        expected_bytes = frame_count * channels * sample_width
        if len(frames) != expected_bytes:
            raise AudioValidationError("WAV audio data is incomplete")

        samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
        if channels == 2:
            samples = samples.reshape(-1, 2).mean(axis=1)
        if sample_rate != TARGET_SAMPLE_RATE:
            target_count = round(samples.size * TARGET_SAMPLE_RATE / sample_rate)
            source_positions = np.arange(samples.size, dtype=np.float64) / sample_rate
            target_positions = np.arange(target_count, dtype=np.float64) / TARGET_SAMPLE_RATE
            samples = np.interp(target_positions, source_positions, samples).astype(np.float32)

        rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
        if not np.isfinite(rms) or rms < 0.001:
            raise AudioValidationError("Audio contains no detectable speech-level signal")
        peak = float(np.max(np.abs(samples)))
        if not np.isfinite(peak) or peak <= 0:
            raise AudioValidationError("Audio contains no usable signal")
        gain = min(0.95 / peak, 8.0)
        return np.clip(samples * gain, -1.0, 1.0).astype(np.float32)

    @staticmethod
    def chunks(samples: NDArray[np.float32]) -> list[AudioChunk]:
        chunk_size = CHUNK_SECONDS * TARGET_SAMPLE_RATE
        overlap_size = CHUNK_OVERLAP_SECONDS * TARGET_SAMPLE_RATE
        if samples.size <= chunk_size:
            return [AudioChunk(0.0, samples)]

        step = chunk_size - overlap_size
        return [
            AudioChunk(start / TARGET_SAMPLE_RATE, samples[start : start + chunk_size])
            for start in range(0, samples.size, step)
        ]

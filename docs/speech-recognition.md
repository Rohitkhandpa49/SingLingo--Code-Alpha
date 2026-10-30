# Speech recognition

The speech-to-sign composer supports temporary Hindi/English audio capture and transcript review. Browser capture converts MediaRecorder output to mono, 16-bit PCM WAV at 16 kHz. Only the WAV is uploaded to the authenticated `POST /api/v1/speech/transcribe` endpoint. The backend validates file type, size, duration, signal level, and selected/detected language before invoking the optional Whisper provider.

The multipart form accepts:

| Field | Requirement | Description |
| --- | --- | --- |
| `audio` | Required | PCM WAV; mono/stereo, 16-bit, 8–48 kHz |
| `language` | Optional | `auto`, `en`, or `hi`; defaults to `auto` |
| `session_id` | Optional | Client-generated UUID for correlating one temporary capture |

Default maximums are 4,000,000 bytes and 60 seconds. Configure `SPEECH_MAX_AUDIO_BYTES` and `SPEECH_MAX_DURATION_SECONDS` to change them. Requests are authenticated and rate-limited. Files are read into memory for inference and closed after processing; no raw audio or transcript is written to MongoDB or translation history. The frontend keeps the transcript editable and does not send it to the sign-translation path.

The provider processes audio in 30-second chunks with a 1-second overlap, then deduplicates overlapping text. This is bounded chunked transcription, not streaming recognition. Chunk-boundary deduplication can affect intentional repetition; users should review the result. Hindi/English detection is limited to Whisper's output and is not a language-understanding or translation feature.

`WHISPER_MODEL` is unset by default. An unconfigured or unavailable provider returns a safe service error; it never substitutes a fake transcript. See [Whisper setup](whisper-setup.md) for installation and model configuration. Unit tests use a deterministic fake provider; they do not prove Whisper model quality, device compatibility, or live transcription performance.

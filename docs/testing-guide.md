# Testing guide

Run frontend checks from `frontend/`:

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

Run backend tests from the repository root:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests
```

The backend tests use an in-memory database double and cover authentication, session revocation, profile/preferences, password-reset token lifecycle, account deletion and retry behavior, cross-origin rejection, history ownership and filters, raw-media rejection, normalized landmark validation, WebSocket origin/session behavior, connection limits, message rate limits, heartbeat, ordering, bounded sends, vocabulary gating/version compatibility, sequence interpretation, exact text-to-sign mapping, ambiguity and unsupported spans, avatar registry validation, feedback authorization, WAV validation/preprocessing, Whisper provider loading, transcription, and authenticated speech uploads. They do not require a live MongoDB instance, SMTP server, Whisper installation/model weights, webcam, verified vocabulary data, avatar assets, or trained checkpoint.

The frontend tests cover registration validation, normalized landmark handling, speech capture encoding, transcript review, browser TTS behavior, explicit translation-history saving, unavailable avatar assets, and sequence playback state transitions. Camera access, MediaPipe, microphone permission, actual Whisper inference, and real WebGL/GLB animation playback are not exercised against physical devices/models by the automated suite. Tests must verify outcomes and error cases, not only that code executes.

The sign-camera tests mock `getUserMedia`, MediaPipe initialization, WebSocket, and animation frames. They cover permission denial, detector initialization failure, a no-hands result, and track cleanup; they do not prove physical webcam behavior. The pure temporal sequence tests cover bounded windows, invalid/out-of-order frames, and reset behavior.

AI-engine unit tests require the isolated environment and use small in-memory synthetic fixtures only for code-path checks. They do not train or evaluate a production model:

```powershell
Set-Location ai-engine
.venv\Scripts\python.exe -m pytest tests
```

Actual model evaluation requires a documented, licensed dataset with explicit train/validation/test splits. No meaningful recognition-quality result is available until such a dataset is provided.

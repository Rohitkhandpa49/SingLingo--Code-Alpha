# Setup guide

## Requirements

- Windows with PowerShell
- Docker Desktop and Docker Compose
- Node.js 20.9 or later and npm
- Python 3.11 or later

## Environment

From the repository root:

```powershell
Copy-Item .env.example .env
```

Edit `.env`. Use a unique random `JWT_SECRET` of at least 32 bytes. Keep `.env` local; `.gitignore` excludes it. The example database credentials are development placeholders, not production credentials.

The frontend and backend also have per-service `.env.example` templates. The backend reads the `.env` in its process working directory; the commands below run it from the repository root and use the root `.env`. The frontend defaults to the local API URL shown in its template.

Password reset is disabled until SMTP is configured. To enable it, set `SMTP_HOST` and `SMTP_FROM_EMAIL` in `.env`; configure `SMTP_PORT` as needed and set `SMTP_USERNAME` and `SMTP_PASSWORD` together only when the relay requires authentication. Authenticated SMTP requires `SMTP_STARTTLS=true`. Set `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` to choose a reset-link lifetime (default 30 minutes). Do not commit mail credentials. Verify actual delivery with your chosen provider before enabling recovery for users.

## Local MongoDB

```powershell
docker compose config
docker compose up -d mongodb
docker compose ps
```

The Compose service exposes MongoDB only on the local loopback interface and persists data in the `mongodb_data` named volume. It does not expose a production service. Stop it with:

```powershell
docker compose stop mongodb
```

Deleting the local database is destructive. Only run `docker compose down --volumes` if you intend to remove the MongoDB data volume.

## Frontend (Phase 2+)

From the repository root:

```powershell
Copy-Item frontend\.env.example frontend\.env.local
Set-Location frontend
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:3000`. Frontend checks:

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

Account, profile, and translation-history screens use the backend API. The sign-to-speech screen requests camera permission only after the user starts tracking. Configure `NEXT_PUBLIC_MEDIAPIPE_WASM_URL` and `NEXT_PUBLIC_HAND_LANDMARKER_MODEL_URL` in `frontend/.env.local`; keep the WASM URL version aligned with `@mediapipe/tasks-vision`. MediaPipe processes frames in the browser; only validated landmarks are sent to the authenticated WebSocket, and no camera frames are sent or stored. Classification remains unavailable until a compatible model is configured. The Phase 8 interpreter and Phase 10 text-to-sign lookup require curated, verified entries in `supported_signs`, a matching `ISL_VOCABULARY_VERSION`, and compatible metadata; none is bundled. Speech-to-sign uses exact reviewed vocabulary matches and does not provide general ISL sentence grammar. The page can capture and transcribe Hindi/English audio after the optional Whisper dependency and model are configured. See [speech recognition](speech-recognition.md), [Whisper setup](whisper-setup.md), [text-to-speech](text-to-speech.md), [speech-to-sign](speech-to-sign.md), and [avatar asset registration](avatar-assets.md). The browser synthesizes spoken output for successful verified sign interpretations; no verified signing animations are bundled.

## Backend (Phase 3+)

Start MongoDB using the local development instructions above. From the repository root, create a Python environment, install the backend dependencies, and start FastAPI:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

The backend reads `.env` from the process working directory. When following these commands from the repository root, edit the root `.env` created above with a replaced `JWT_SECRET` and matching MongoDB credentials. `backend/.env.example` documents the same backend variables if you run the service from `backend/`.

```powershell
backend\.venv\Scripts\python.exe backend\run.py
```

The runner reads `BACKEND_HOST` and `BACKEND_PORT` from the root `.env`; defaults are `0.0.0.0:8000`. It enables reload only when `APP_ENV=development`. The API is available at `http://localhost:8000`; development OpenAPI docs are at `http://localhost:8000/docs`. Check `http://localhost:8000/health` before using the frontend. The frontend at `http://localhost:3000` uses the API base URL from `frontend/.env.local` or its documented localhost default. The API supports registration, login/logout, session/profile lookup and updates, password reset when SMTP is configured, account deletion, authenticated history create/list/delete, and authenticated landmark inference at `/api/v1/ws/gestures`. Browser state-changing requests require the configured frontend origin.

MongoDB pool and connection timeouts can be configured through `MONGODB_MAX_POOL_SIZE`, `MONGODB_MIN_POOL_SIZE`, `MONGODB_MAX_IDLE_TIME_MS`, `MONGODB_CONNECT_TIMEOUT_MS`, `MONGODB_SERVER_SELECTION_TIMEOUT_MS`, and optional `MONGODB_WAIT_QUEUE_TIMEOUT_MS`. Defaults match PyMongo's defaults. Tune these values only after measuring workload concurrency and the database deployment's connection limits.

The gesture WebSocket limits are configurable through `WEBSOCKET_MAX_MESSAGE_BYTES`, `WEBSOCKET_HEARTBEAT_INTERVAL_SECONDS`, `WEBSOCKET_HEARTBEAT_TIMEOUT_SECONDS`, `WEBSOCKET_RATE_LIMIT_PER_MINUTE`, `WEBSOCKET_MAX_CONNECTIONS_PER_USER`, `WEBSOCKET_SEND_TIMEOUT_SECONDS`, `WEBSOCKET_SEQUENCE_MAX_AGE_SECONDS`, and `WEBSOCKET_SESSION_RECHECK_SECONDS`. Defaults and close-code behavior are in [websocket-protocol.md](websocket-protocol.md). Connection tracking and rate limits are process-local; run one backend worker until a shared adapter is configured.

At startup the backend additively ensures validators and indexes for the nine collections documented in [database-schema.md](database-schema.md). It does not drop collections or alter existing data. The Atlas database user must be allowed to list/create collections, run `collMod`, and create indexes. Existing collection validators and validation settings are retained and combined with the SignLingo validation rules.

### Optional speech recognition

Speech recognition is disabled when `WHISPER_MODEL` is unset. To enable it, install the optional dependencies into the backend virtual environment:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\speech-requirements.txt
```

Set `WHISPER_MODEL=tiny` (or `base`/`small`) and `WHISPER_DEVICE=cpu` in the root `.env`. The first authenticated transcription request downloads Whisper weights to `WHISPER_DOWNLOAD_ROOT`; ensure the selected model fits the host's available memory and disk. Set `SPEECH_MAX_AUDIO_BYTES` and `SPEECH_MAX_DURATION_SECONDS` to adjust the request bounds. The endpoint accepts PCM WAV, and does not store raw audio or transcript results. Browser capture requires microphone permission and a secure context (localhost is allowed); transcript output should be reviewed before use. Details and the local test route are in [speech-recognition.md](speech-recognition.md).

History retention is disabled unless `HISTORY_RETENTION_DAYS` is set. Cleanup is never automatic. After configuring the value and confirming the database and backup policy, preview the number of eligible records:

```powershell
backend\.venv\Scripts\python.exe backend\purge_history.py
```

Only if that preview is expected, explicitly execute the deletion:

```powershell
backend\.venv\Scripts\python.exe backend\purge_history.py --execute
```

No other collections are automatically expired or removed.

The gesture classifier returns `model_unavailable` by default. To enable inference, provide both `GESTURE_MODEL_PATH` (a TorchScript model) and `GESTURE_LABELS_PATH` (a JSON string array in output-logit order), install PyTorch in the backend environment, and keep the generated `gesture-model.json` beside the checkpoint and labels. Static models accept `[1, 30, 2, 21, 3]`; dynamic models accept `[1, 30, 2, 22, 3]` with an additional camera-space wrist point per hand. Both return `[1, label_count]` logits. Model artifacts and reports are described in [computer-vision-and-recognition.md](computer-vision-and-recognition.md). No training dataset, validated recognition model, or verified ISL vocabulary is bundled. Do not configure unvalidated labels or weights as ISL recognition. See [the vocabulary curation guide](isl-vocabulary-guide.md) before setting `ISL_VOCABULARY_VERSION`.

Run backend tests from the repository root. Tests use an in-memory database double and do not require MongoDB:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests
```

## Later phases

Python requirements are listed separately in `backend/requirements.txt` and `ai-engine/requirements.txt`; AI dependencies include large ML packages and should be installed only when needed. Raw camera and microphone recordings are not persisted by the current application.

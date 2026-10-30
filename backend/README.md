# Backend

FastAPI service for account authentication and management, translation-history operations, MongoDB health checks, and authenticated landmark-sequence WebSocket inference. It uses PyMongo's asynchronous client, one client per application lifespan, and the driver's default pool settings; no workload-specific pool sizes or timeouts are assumed.

## Run locally

From the repository root:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
```

Replace `JWT_SECRET` with at least 32 random bytes. Set the MongoDB credentials in the URI to match the local Compose credentials or configure an Atlas URI. Start MongoDB with `docker compose up -d mongodb`, then run:

```powershell
backend\.venv\Scripts\python.exe backend\run.py
```

The runner reads `BACKEND_HOST` and `BACKEND_PORT` from the root `.env` and enables reload only in development. The API listens on port 8000 by default. Health: `GET /health`; development OpenAPI UI: `/docs`. Browser sessions use an HttpOnly, SameSite=Lax cookie scoped to `/api/v1`; production requires `COOKIE_SECURE=true` and HTTPS/WSS. The `/api/v1/ws/gestures` endpoint accepts only normalized 30-frame hand sequences and does not persist them.

Authentication uses Argon2 password hashes and versioned JWT sessions. Logout and successful password recovery revoke existing sessions. Password recovery requires `SMTP_HOST` and `SMTP_FROM_EMAIL`; optional SMTP credentials must be configured together and are sent only over STARTTLS. Without the required SMTP settings, reset requests return `503` and no token is issued. Tokens are hashed in MongoDB, expire after `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`, and can be consumed once. SMTP delivery was not tested against a live provider.

`PATCH /api/v1/users/me` updates the display name and accessibility/language preferences. `DELETE /api/v1/users/me` requires the current password and removes the account's history, notifications, audio events, feedback, and preferences. Shared conversations retain other participants and remove the deleted account from their participant list. Cleanup precedes user deletion and is safe to retry after an interrupted database operation.

MongoDB pool and timeout settings are configurable with `MONGODB_MAX_POOL_SIZE`, `MONGODB_MIN_POOL_SIZE`, `MONGODB_MAX_IDLE_TIME_MS`, `MONGODB_CONNECT_TIMEOUT_MS`, `MONGODB_SERVER_SELECTION_TIMEOUT_MS`, and optional `MONGODB_WAIT_QUEUE_TIMEOUT_MS`. Defaults match the PyMongo driver defaults. Set pool sizes based on measured application concurrency and Atlas connection limits; no workload-specific sizing is assumed.

The gesture WebSocket enforces cookie authentication and frontend Origin checks, per-user connection and message limits, heartbeat and session-revalidation deadlines, strict Pydantic message validation, and bounded send timeouts. Uvicorn is configured with the message-size and one-message receive-queue limits. The browser reconnects with capped exponential backoff and drops stale windows when its outgoing buffer is high. Configure these controls with the `WEBSOCKET_*` variables in `.env`; see `docs/websocket-protocol.md` for defaults, messages, and close codes.

Connection tracking, rate limits, and inference execution are process-local. Use a single backend worker until a shared connection/broadcast and rate-limit adapter is implemented for multi-worker deployments. Only `/api/v1/ws/gestures` is implemented; speech, conversation, and private-notification sockets are not exposed.

The gesture WebSocket loads a bounded, version-matched verified vocabulary snapshot once per connection and adds a structured `translation` field to the existing gesture response. A single sign or exact, explicitly curated phrase can be translated only when the loaded model version is listed in the vocabulary record. Multi-sign sequences without a validated phrase rule remain partial; general ISL grammar is not inferred. Set `ISL_VOCABULARY_VERSION` only after a qualified review and compatibility check. There are no verified entries in the repository, so translation remains unsupported by default. See `docs/isl-language-engine.md` and `docs/isl-vocabulary-guide.md`.

Authenticated vocabulary lookup endpoints are `GET /api/v1/isl/vocabulary/coverage` and `GET /api/v1/isl/vocabulary/{sign_id}`. `POST /api/v1/feedback` stores user-owned corrections, unknown-sign reports, and usefulness ratings in the existing `feedback` collection with `pending_review`; submissions are never treated as verified data automatically.

Startup additively validates and indexes the nine collections described in `docs/database-schema.md`. The Atlas database user needs collection-list/create, `collMod`, and index-creation permissions. Existing documents are not migrated or deleted. An index conflict caused by existing duplicate data is reported and prevents startup rather than silently changing that data.

Set `HISTORY_RETENTION_DAYS` only if a manual history retention policy is required. Cleanup is disabled by default and is never run automatically. Preview first, then pass the explicit execution flag:

```powershell
backend\.venv\Scripts\python.exe backend\purge_history.py
backend\.venv\Scripts\python.exe backend\purge_history.py --execute
```

## Tests

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests
```

Tests use a small in-memory database double and do not require Atlas or a local MongoDB server. They cover password hashing, session revocation, profile/preferences, reset-token lifecycle, account deletion, origin checks, history ownership, query filters, raw-media rejection, and the gesture WebSocket's authentication and model-unavailable response.

The gesture classifier returns `model_unavailable` unless both `GESTURE_MODEL_PATH` and `GESTURE_LABELS_PATH` are configured. It loads a CPU TorchScript model; static models accept `[1, 30, 2, 21, 3]`, while dynamic models accept `[1, 30, 2, 22, 3]` including camera-space wrist positions, and both return one logits vector. Keep the generated `gesture-model.json` beside the model and labels for model-type/schema validation. Install a compatible PyTorch build in the backend environment and restart the API. The default SlowAPI HTTP rate limiter uses in-process memory; use shared rate-limit storage for multi-worker HTTP deployments. Do not store raw camera footage or microphone recordings.

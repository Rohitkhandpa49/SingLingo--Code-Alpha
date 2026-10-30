# API documentation

Base path: `/api/v1`. The interactive OpenAPI document is served by FastAPI at `/docs` in development.

## Health

| Method | Path | Auth | Behavior |
| --- | --- | --- | --- |
| `GET` | `/health` or `/api/v1/health` | No | Backward-compatible readiness check; pings MongoDB |
| `GET` | `/api/v1/health/ready` | No | Checks MongoDB connectivity; returns `503` if unavailable |
| `GET` | `/api/v1/health/live` | No | Process liveness only; does not query MongoDB |

## Authentication

| Method | Path | Auth | Behavior |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | No | Creates an account and establishes a session; `409` for duplicate email |
| `POST` | `/auth/login` | No | Authenticates credentials and establishes a session |
| `POST` | `/auth/logout` | Optional | Revokes all current account sessions and clears the session cookie |
| `GET` | `/auth/me` | Yes | Returns the current account |
| `POST` | `/auth/password-reset/request` | No | Sends a one-time reset link; disabled until SMTP is configured |
| `POST` | `/auth/password-reset/confirm` | No | Consumes an unexpired reset token and revokes existing sessions |
| `GET` | `/users/me` | Yes | Returns the current account profile |
| `PATCH` | `/users/me` | Yes | Updates the display name and accessibility/language preferences |
| `DELETE` | `/users/me` | Yes | Deletes the account's associated personal data; requires the current password |

Successful registration and login set an `HttpOnly`, `SameSite=Lax` JWT cookie scoped to `/api/v1`. `Secure` is enabled for production. The API also accepts a Bearer access token for non-browser clients. Invalid or expired sessions receive `401` without revealing account details.

Successful registration and login set an `HttpOnly`, `SameSite=Lax` JWT cookie scoped to `/api/v1`. `Secure` is enabled for production. The API also accepts a Bearer token for non-browser clients. Invalid, expired, or revoked sessions receive `401` without revealing account details. Browser unsafe requests must include the configured frontend `Origin`; cookie requests without an Origin are rejected outside tests.

For password recovery, configure `SMTP_HOST` and `SMTP_FROM_EMAIL`; username/password authentication requires STARTTLS. The API returns `503` if SMTP is not configured or delivery fails. Unknown email addresses receive a generic response. Reset tokens are not returned by the API, stored as hashes, expire after the configured lifetime, and cannot be reused.

Account deletion removes user-owned history, notifications, audio events, feedback, and preferences. Shared conversations are retained with the deleted user removed from the participant list. Cleanup is performed before the user document is deleted, so a failed operation can be safely retried.

## Translation history

| Method | Path | Auth | Behavior |
| --- | --- | --- | --- |
| `POST` | `/history` | Yes | Stores user-supplied text metadata for a completed translation |
| `GET` | `/history` | Yes | Lists the caller's entries; supports `search`, `language`, `created_after`, `created_before`, `limit`, and `skip` |
| `DELETE` | `/history/{entry_id}` | Yes | Deletes only an entry owned by the caller; returns `404` otherwise |

History schemas reject unknown fields, including raw media fields. The current service does not perform translation; clients should only create records for completed translation output.

## ISL vocabulary and feedback

| Method | Path | Auth | Behavior |
| --- | --- | --- | --- |
| `GET` | `/isl/vocabulary/coverage` | Yes | Reports the configured version, verified counts, available languages, and whether sentence grammar is present |
| `GET` | `/isl/vocabulary/{sign_id}` | Yes | Looks up a record only when it is verified and matches `ISL_VOCABULARY_VERSION` |
| `POST` | `/isl/translate-text` | Yes | Maps text to exact verified single-sign/phrase vocabulary entries; reports unsupported spans and never invents sentence grammar |
| `POST` | `/feedback` | Yes | Submits correction, unknown-sign, or usefulness feedback for review |

Feedback is stored under the authenticated user's ID and always starts as `pending_review`. Feedback is not promoted to vocabulary or training data automatically. No verified vocabulary records ship with the repository; without a curated version, lookup returns `404` and gesture results remain unsupported.

Text mapping accepts JSON `{ "text": "...", "language": "auto|en|hi" }` and is limited to 30 requests/minute per process. Automatic detection uses script cues only; mappings are exact verified dictionary entries, not general language translation. Unmatched and ambiguous spans are returned explicitly. Saving a successful result is a separate, explicit client call to `POST /history`.

## Speech recognition

| Method | Path | Auth | Behavior |
| --- | --- | --- | --- |
| `POST` | `/speech/transcribe` | Yes | Accepts a bounded PCM WAV upload and returns a final Hindi/English Whisper transcript |

The optional model is disabled until configured. The endpoint does not persist the audio or transcript; see [speech recognition](speech-recognition.md) and [Whisper setup](whisper-setup.md).

## Real-time landmark inference

| Transport | Path | Auth | Behavior |
| --- | --- | --- | --- |
| WebSocket | `/ws/gestures` (under `/api/v1`) | Session cookie | Accepts normalized landmark sequences and returns a classifier status/result |

The WebSocket requires the configured frontend `Origin` and an authenticated session. It accepts JSON text messages only; binary media messages are closed with code `1003`. A sequence contains exactly 30 frames sampled at 10 Hz; each frame contains zero to two hands, with 21 wrist-centered points per hand. Coordinates are finite values in `[-1, 1]`. Unknown fields (including video or image data) are rejected. Message size, per-user rate, per-user connections, heartbeat and send deadlines are configurable. The server serializes inference and bounded sends; the browser drops stale overlapping windows when its outbound buffer is full. Responses use `model_unavailable` until a TorchScript model and its ordered JSON label list are configured; low-confidence predictions return `unknown`.

The WebSocket performs gesture inference and emits an additive language-interpretation result. It only returns a single-sign translation or an exact verified phrase match; multi-sign output without validated grammar remains partial. Heartbeat format, ordering and replay checks, reconnect behavior, close codes, and the process-local scaling limitation are documented in [websocket-protocol.md](websocket-protocol.md).

The TorchScript model input shape is `[1, 30, 2, 21, 3]` (`batch, frames, left/right hands, points, xyz`) and its output must be `[1, label_count]` logits. The default configuration does not import PyTorch or claim ISL recognition.

## Security behavior

- CORS allows only the configured `FRONTEND_ORIGIN` and credentialed requests.
- SlowAPI applies a process-local default limit of 100 requests/minute and tighter limits to registration and login. Production multi-worker deployments should use shared rate-limit storage.
- API validation errors use FastAPI's structured `422` response. Authentication failures use generic messages.

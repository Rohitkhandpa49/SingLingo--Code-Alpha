# MongoDB collections and indexes

The backend uses PyMongo 4.13+ asynchronous operations with one client per application lifespan. Startup pings the selected database, ensures collection validators, and creates indexes idempotently. Startup never drops collections, indexes, or documents. The client closes when the application lifespan ends, including when database initialization fails.

## Collections

| Collection | Purpose and access pattern |
| --- | --- |
| `users` | Account identity, password hash, session version, bounded profile/accessibility preferences, and hashed expiring password-reset token metadata. Email is unique. Existing account fields and IDs are preserved. |
| `translation_history` | User-requested completed translation records only. Reads and deletes are scoped by `user_id`; history is paginated by creation time. |
| `supported_signs` | Versioned sign vocabulary metadata, explicit language translations, model compatibility, phrase sequences, and verified asset references. Only `verification_status=verified` records with matching configured versions are exposed as translations. |
| `conversations` | Conversation ID, up to two participant references, preferences, and lifecycle timestamps. No message content is persisted here. |
| `notifications` | Per-user visual notifications with priority and read status. Retrieval and mutation are scoped to the owning user. |
| `audio_events` | User-requested event metadata only. No raw audio or unsupported sound classification is stored. |
| `feedback` | User-scoped correction and rating records with session/sign references and a `pending_review` verification status; submissions are not automatically training data. |
| `model_versions` | Model metadata, dataset references, evaluation metrics, and deployment status; no model binaries are stored in MongoDB. |
| `user_preferences` | One preference document per user, keyed by a unique `user_id`. |

Per-collection Pydantic documents validate application writes and reads. MongoDB `$jsonSchema` validators provide a second validation layer. New collections are created with strict/error validation. Existing collections are updated with `collMod` using `moderate` validation by default, so old nonconforming records are not rewritten or blocked from reads; existing validators and their validation settings are preserved and combined with SignLingo's rules. Existing documents are never migrated or deleted automatically.

## Indexes

| Collection | Index | Use |
| --- | --- | --- |
| `users` | unique `email` | Login lookup and duplicate-account prevention |
| `users` | sparse `password_reset_token_hash` | Lookup of active one-time password-reset tokens |
| `translation_history` | `user_id`, descending `created_at` | User-scoped, newest-first history pages |
| `supported_signs` | unique `sign_id`, `language` | Vocabulary identity; same sign ID may exist in different languages |
| `supported_signs` | `language`, `sign_category`, `sign_name` | Language/category browse |
| `supported_signs` | `language`, `verification_status`, `vocabulary_version` | Load only the configured verified vocabulary snapshot |
| `conversations` | unique `conversation_id` | Conversation lookup |
| `conversations` | `participants`, descending `started_at` | Participant conversation list |
| `notifications` | `user_id`, `read_status`, descending `created_at` | User's unread/read notification pages |
| `audio_events` | `user_id`, descending `created_at` | User's event history |
| `feedback` | `user_id`, descending `created_at` | User feedback history |
| `feedback` | `translation_id`, descending `created_at` | Translation feedback review |
| `model_versions` | unique `model_name`, `version` | Model version identity |
| `model_versions` | `model_name`, `deployment_status` | Deployment lookup |
| `user_preferences` | unique `user_id` | One preference document per account |

Indexes are created idempotently at startup. Unique-index creation will fail safely if pre-existing data violates uniqueness; startup reports the database error instead of removing or rewriting conflicting documents. Index removal and automated index migrations are intentionally not performed.

## Repositories, queries, and failures

`UserRepository` and `HistoryRepository` retain their existing auth/history interfaces and validate documents through Pydantic before persistence and after retrieval. The typed domain repositories in `backend/app/database/repositories/documents.py` provide create/read/update/delete, bounded pagination, allow-listed filters and sorting, escaped text search, and bounded aggregation for supported signs, conversations, notifications, audio events, feedback, model versions, and user preferences. User-owned repository methods include the owner ID in the MongoDB query itself.

Authentication adds a backward-compatible `session_version` default of zero, so existing user documents and JWTs remain valid until logout or password reset. Reset token hashes are removed when used or when mail delivery fails; no raw reset token is stored. Profile accessibility settings are embedded on the user document for account/profile reads, while `user_preferences` remains available for typed domain preferences.

Offset pagination uses `limit` (maximum 100) and `skip` (maximum 1,000,000) to preserve existing API contracts. Deep pagination may require a keyset cursor as datasets grow. Case-insensitive substring search uses escaped regular expressions and is not guaranteed to use an index; Atlas Search should be evaluated before adding broad text indexes.

MongoDB operation failures return a generic `503` response and are logged without connection strings or server error messages. Invalid stored documents produce a sanitized server error with the collection and route logged, not document values.

## Retention and privacy

Camera frames are processed locally in the browser. The backend receives bounded landmark sequences over WebSocket and does not persist live sequences or predictions. The application does not accept or persist raw microphone recordings. Only completed translations explicitly saved by the user belong in history.

`HISTORY_RETENTION_DAYS` is optional and unset by default. No TTL index or startup cleanup is used because either could delete existing records without an operator action. With retention configured, `backend/purge_history.py` previews expired-record counts by default. Data is deleted only when an operator explicitly reruns it with `--execute`. Review backups and retention requirements before doing so.

Account deletion is an explicit user request, not a startup/retention action. The service removes the account's history, notifications, audio events, feedback, and preferences; shared conversation documents retain remaining participants. It deletes the user document last so an interrupted cleanup can be retried. MongoDB transactions are not currently used for this multi-collection operation.

## Atlas setup notes

Configure `MONGODB_URI` with an Atlas connection string and `MONGODB_DATABASE` with the target database. The application identity needs permissions to list/create collections, run `collMod` on existing collections, and create indexes. Atlas connectivity, permissions, index builds, and query performance must be verified against the actual deployment; local fake-database tests do not establish Atlas readiness. Before rollout, inspect existing validators, duplicate values for unique-index keys, Atlas connection limits, and representative query plans.

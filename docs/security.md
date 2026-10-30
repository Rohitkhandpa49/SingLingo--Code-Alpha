# Security baseline

- Keep secrets in environment variables; never commit `.env` or credentials.
- Use a unique, high-entropy JWT secret outside development.
- Restrict MongoDB Atlas users and network access to the minimum required.
- Keep the local MongoDB Compose port bound to loopback.
- Validate API input, enforce authentication/authorization, and limit request rates.
- Use HTTPS/WSS in deployed environments and configure an explicit CORS allowlist.
- Do not persist raw camera or microphone recordings by default.
- Validate uploads and return safe errors without exposing internal details.

The backend hashes passwords with Argon2, requires a replaced 32-byte JWT secret, uses HTTP-only SameSite cookies for browser sessions, restricts CORS and unsafe browser requests to one configured frontend origin, validates request schemas, and scopes account operations by authenticated user. Unsafe requests from another browser origin are rejected; cookie-authenticated unsafe requests without an Origin are rejected outside tests. Production configuration rejects an insecure cookie setting.

JWTs carry a session version checked against the account record. Logout increments it, revoking all existing sessions; password reset does the same. Password-reset tokens are high-entropy, stored only as SHA-256 hashes, expire, and are atomically consumed once. The endpoint is disabled until `SMTP_HOST` and `SMTP_FROM_EMAIL` are configured. Configure SMTP authentication only with STARTTLS. SMTP delivery and mail-provider configuration must be tested in the deployment environment.

Account deletion requires the current password. It removes the account and its history, notifications, audio events, feedback, and preferences. Shared conversation records retain non-deleted participants. Data cleanup runs before deleting the user record and can be retried after an interrupted database operation; MongoDB multi-collection transactions are not currently used.

The gesture WebSocket additionally checks the browser Origin and session cookie, limits messages to 100 KB, accepts only finite normalized landmarks, and never writes sequences to MongoDB.

Camera frames are processed locally by MediaPipe in the browser. Only normalized landmark coordinates are sent to the authenticated backend; a trained model is not configured by default, so results remain unknown. Configure only validated TorchScript weights and a reviewed label list.

The HTTP and WebSocket rate limiters, plus the WebSocket connection registry, are process-local and are not sufficient for a multi-worker deployment. WebSocket connection and per-user message limits are configurable and shared across reconnects within a worker, but workers do not share counters or connections. Use one worker or introduce distributed rate limiting and pub/sub before scaling horizontally. The WebSocket protocol and limitations are documented in [websocket-protocol.md](websocket-protocol.md). This baseline is not a security review or a production-ready deployment.

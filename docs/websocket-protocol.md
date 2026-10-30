# SignLingo real-time WebSocket protocol

## Implemented endpoint

The currently implemented endpoint is `wss://<api-host>/api/v1/ws/gestures` (use `ws://` for local development). It accepts the existing HTTP-only `signlingo_access` cookie and requires an exact match to the configured frontend `Origin`.

The speech, conversation, and private-notification WebSocket endpoints are not implemented. Do not treat this gesture endpoint as a general conversation or audio transport.

The endpoint authenticates with the existing HTTP-only session cookie; bearer/query-token authentication is not supported.

## Landmark request

Requests are UTF-8 JSON text messages. The legacy fields are retained:

```json
{
  "type": "landmark_sequence",
  "sequence_id": "00000000-0000-0000-0000-000000000001",
  "sequence": 1,
  "timestamp": "2026-10-30T12:00:00Z",
  "schema_version": "1.0",
  "session_id": "00000000-0000-0000-0000-000000000002",
  "output_language": "en",
  "frame_width": 640,
  "frame_height": 480,
  "sample_rate_hz": 10,
  "frames": [{
    "hands_detected": 1,
    "hands": [{
      "handedness": "Right",
      "confidence": 0.9,
      "wrist": { "x": 0.5, "y": 0.5, "z": 0.0 },
      "points": [{ "x": 0.0, "y": 0.0, "z": 0.0 }]
    }]
  }]
}
```

The JSON above abbreviates `frames` and `points` for readability; a valid request still needs exactly 30 frames and 21 point objects per present hand.

`schema_version`, `session_id`, output language, frame dimensions, detected-hand count, per-hand wrist, and confidence are additive metadata; older clients can omit them. Output language is `en` or `hi`, defaulting to `en`. `sequence` and timezone-aware `timestamp` are an optional pair. Updated clients send them. The sequence number must increase on a connection; timestamps must increase, not be older than `WEBSOCKET_SEQUENCE_MAX_AGE_SECONDS`, and not be more than one minute in the future. Recent sequence IDs are rejected if replayed on the same connection. `frames` contains exactly 30 frames; each frame contains zero to two uniquely handed hands with exactly 21 finite normalized points each. `points` are wrist-centered and hand-scale-normalized XYZ values in `[-1, 1]`; `wrist` is camera-space MediaPipe XYZ and preserves translation between frames for dynamic classifiers. Hand confidence is a separate `[0, 1]` score, not a landmark coordinate. Unknown fields (including raw audio, image or video) are rejected.

The browser processes frames locally using MediaPipe Tasks Vision. It sends compact landmarks only, with bounded overlapping windows; it never uploads image or video bytes. WASM and task model URLs are configured by `NEXT_PUBLIC_MEDIAPIPE_WASM_URL` and `NEXT_PUBLIC_HAND_LANDMARKER_MODEL_URL`.

Successful requests receive the existing response:

```json
{
  "type": "gesture_result",
  "sequence_id": "00000000-0000-0000-0000-000000000001",
  "status": "model_unavailable",
  "label": null,
  "confidence": null,
  "model_version": null,
  "translation": {
    "type": "isl_translation",
    "translation_id": "00000000-0000-0000-0000-000000000004",
    "status": "unsupported",
    "session_id": "00000000-0000-0000-0000-000000000002",
    "sequence_id": "00000000-0000-0000-0000-000000000001",
    "recognized_signs": [],
    "interpreted_text": "",
    "language": "en",
    "confidence": null,
    "translation_level": "partial",
    "unsupported_segments": [
      { "sign_id": null, "reason": "recognition_model_unavailable" }
    ],
    "model_version": null,
    "vocabulary_version": null,
    "timestamp": "2026-10-30T12:00:00Z"
  }
}
```

The response includes an additive `translation` object; old clients may ignore it. Only entries marked verified, matching the configured vocabulary version, and explicitly compatible with the loaded model version can be translated. Repeated overlapping model labels are collapsed within a session. A single verified sign or an exact verified phrase mapping may return text; unmatched labels remain unsupported and multi-sign sequences without a validated phrase rule do not become sentences. Classifier errors return a generic `error` event; implementation details are logged by exception type only. No landmark sequence or model output is persisted.
When a configured model receives a sequence with no detected hands, it returns `unknown` with a null label and confidence. Dynamic models require camera-space wrist coordinates for every detected hand; missing wrist data returns a generic classifier error rather than producing a misleading prediction.

## Heartbeat and reconnect

When no application message has arrived for `WEBSOCKET_HEARTBEAT_INTERVAL_SECONDS`, the server sends:

```json
{ "type": "system.heartbeat", "action": "ping", "nonce": "opaque-random-value" }
```

The client must echo the nonce in a `system.heartbeat` `pong` response. A missing response within `WEBSOCKET_HEARTBEAT_TIMEOUT_SECONDS` closes the connection with code `4408`. The browser client answers server heartbeats and reconnects with capped exponential backoff; it stops retrying after five consecutive failures and can be restarted with the camera controls.

Sessions are checked at connection time and revalidated every `WEBSOCKET_SESSION_RECHECK_SECONDS`; revoked or expired sessions close with `4401`. The per-user concurrent connection limit and rate limit are enforced by the current process.

## Limits, backpressure, and close codes

| Setting | Default | Behavior |
| --- | ---: | --- |
| `WEBSOCKET_MAX_MESSAGE_BYTES` | 100000 | Application and Uvicorn inbound message limit |
| `WEBSOCKET_RATE_LIMIT_PER_MINUTE` | 120 | Per-user message cap across connections in one worker |
| `WEBSOCKET_MAX_CONNECTIONS_PER_USER` | 3 | Active connection cap per user per worker |
| `WEBSOCKET_SEND_TIMEOUT_SECONDS` | 5 | Slow outbound sends close with `1013` |
| `WEBSOCKET_HEARTBEAT_INTERVAL_SECONDS` | 20 | Idle interval before application heartbeat |
| `WEBSOCKET_HEARTBEAT_TIMEOUT_SECONDS` | 45 | Heartbeat response deadline |
| `WEBSOCKET_SHUTDOWN_TIMEOUT_SECONDS` | 10 | Uvicorn graceful-shutdown deadline |

Inference is serialized per connection, so there is no unbounded application-level work queue or reordering of final results. Uvicorn's inbound WebSocket queue is set to one message. The browser caps its outgoing `bufferedAmount` and drops the oldest overlapping landmark windows under backpressure. Final speech/conversation event prioritization is not applicable until those event types are implemented.

Close codes: `4401` unauthenticated/revoked session; `4403` invalid Origin; `4408` heartbeat timeout; `4429` connection or message rate limit reached; `1003` binary/non-text message; `1009` oversized payload; `1012` graceful server shutdown; `1013` service unavailable or slow consumer.

## Scaling and limitations

The connection registry and rate limiter are in-process. With multiple workers, a user can obtain up to the per-worker connection/rate allowance, and workers cannot broadcast to each other's connections. The current backend is not configured for distributed WebSocket coordination; deploy one worker or put a shared pub/sub and distributed rate-limit adapter behind the manager before scaling out. The WebSocket remains gesture-only; conversation membership/session IDs and audio payload schemas are not implemented.

# ISL language understanding

## Scope and limitations

The backend separates gesture classification from language interpretation. A gesture label is treated as an identifier, not as an English word. It becomes a translation only when an explicitly verified `supported_signs` record matches the configured vocabulary version, the requested output language, and the classifier's model version.

This repository contains **no verified vocabulary entries, validated phrase mappings, complete ISL grammar rules, trained recognition checkpoint, or measured vocabulary coverage**. Until curated records and a compatible model are configured, classified model labels remain unsupported and no text is synthesized as a verified translation. This is a limited vocabulary architecture, not a complete ISL translator.

The interpreter can return a translation for one verified sign or an exact ordered sequence with an explicitly verified phrase mapping. It does not infer general sentence grammar, rearrange English word order, fill in unknown signs, or construct sentences by concatenating individual glosses. Multi-sign sequences without an exact phrase mapping are marked partial and have no interpreted sentence text.

## Data flow

1. The authenticated `/api/v1/ws/gestures` connection loads a bounded, per-connection snapshot of vocabulary records matching `ISL_VOCABULARY_VERSION`.
2. The classifier returns its status, label, confidence, and model version.
3. Low-confidence, unknown, and unavailable predictions are preserved as such.
4. A classified label is resolved only against verified vocabulary records compatible with that exact model version.
5. Repeated overlapping labels are collapsed within the current session.
6. Exact verified phrase sequences can produce phrase text. No other multi-sign grammar is assumed.
7. An additive `translation` object accompanies the existing `gesture_result` event. Landmark sequences and predictions are not persisted.

The interpretation buffer is isolated per WebSocket connection and reset when the supplied session ID, output language, or model version changes. It is bounded to 32 recognized signs. Repeated identical signs are collapsed until a non-classified prediction creates a boundary; the system cannot distinguish an intentional repeated sign from overlapping-window duplication without validated movement/segmentation data.

## Vocabulary and model compatibility

Set `ISL_VOCABULARY_VERSION` only after a curator has entered and verified vocabulary records. Each record requires a version, explicit translations, `verification_status=verified`, and one or more exact compatible model versions. Phrase records additionally require an ordered `sequence_sign_ids` list referencing verified signs. See [the vocabulary guide](isl-vocabulary-guide.md).

Model metadata in `gesture-model.json` supplies the classifier model version. Legacy metadata-free checkpoints can still classify as before, but have no model version and therefore cannot produce verified translations.

## API

- `GET /api/v1/isl/vocabulary/coverage` (authenticated) reports the configured version, verified sign/phrase counts, available output languages, and whether sentence grammar is available.
- `GET /api/v1/isl/vocabulary/{sign_id}` (authenticated) returns only a verified record for the configured vocabulary version.
- `POST /api/v1/feedback` (authenticated) accepts correction, unknown-sign, or usefulness feedback associated with the authenticated user and caller-supplied translation/session IDs. Every record starts as `pending_review`; feedback never becomes verified training data automatically.

Feedback request example:

```json
{
  "translation_id": "00000000-0000-0000-0000-000000000001",
  "session_id": "00000000-0000-0000-0000-000000000002",
  "feedback_type": "correction",
  "rating": 2,
  "correction": "A user-provided correction awaiting review",
  "sign_id": "the-model-label-being-reviewed"
}
```

Feedback is private to the authenticated user in MongoDB. The service does not check the supplied session ID against a persistent conversation because current gesture sessions are not persisted; the server always derives `user_id` from the authenticated session.

## Tests and operational checks

Run Phase 8 backend tests from the repository root:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_isl_engine.py backend\tests\test_feedback_api.py backend\tests\test_realtime_api.py -q
```

Tests use synthetic, clearly test-only vocabulary records and an in-memory database double. They validate policy and contracts, not actual ISL meanings, model accuracy, Atlas connectivity, or a full translation workflow.

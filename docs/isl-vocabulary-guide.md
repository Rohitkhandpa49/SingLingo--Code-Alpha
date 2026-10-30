# ISL vocabulary curation guide

## Source and verification policy

No verified ISL vocabulary dataset is bundled with SignLingo. Do not copy unlicensed material or mark a record verified merely to make a demo translate. A qualified ISL reviewer must establish the sign meaning, language variant, source/license, metadata, and approved output translations. Keep dataset references and provenance traceable.

The currently configured database contains no vocabulary records as part of this repository's fixtures. The API reports zero entries when no version is configured. This is expected and intentionally produces unsupported translations rather than guessed meanings.

## `supported_signs` record contract

Records use the existing MongoDB `supported_signs` collection. Existing sign metadata remains intact. Translation requires all of the following:

- `language` is `isl`.
- `verification_status` is `verified`.
- `vocabulary_version` exactly matches `ISL_VOCABULARY_VERSION`.
- `translation_texts` has non-empty values for supported output languages (`en`, `hi`).
- `compatible_model_versions` includes the classifier's exact `model_version`.
- Sign labels emitted by the model equal the record's stable `sign_id`.

Optional descriptive fields include `hand_configuration`, `movement_description`, `hand_orientation`, `dominant_hand`, `facial_expression`, `body_posture`, and `dataset_reference`.

An exact phrase record uses its own stable `sign_id`, a `sequence_sign_ids` array containing at least two ordered sign IDs, and explicit translations. Every referenced ID must resolve to a verified sign in the same vocabulary version. This is a curated phrase mapping, not a general grammar rule. Arbitrary lists of mapped signs are never joined into sentences.

The speech-to-sign lookup uses exact normalized `translation_texts` values to map Hindi/English text back to a single sign or an explicit phrase record. It uses longest exact phrase matching, reports ambiguous and unmatched spans, and marks independent word sequences partial because sentence grammar is unavailable. It does not use a language model or guess synonyms. The reverse text lookup requires the configured verified vocabulary version; it does not run gesture inference.

Avatar playback is separately gated by the server's `DEFAULT_AVATAR_ASSET_REGISTRY`. A database `animation_asset` reference alone is not enough to enable playback; the stable sign ID, registered local GLB path, and named clip must all match. See [the avatar asset guide](avatar-assets.md).

## Versioning and safe rollout

1. Obtain appropriately licensed materials and qualified review.
2. Add records using a controlled, authenticated administrative process. No public vocabulary-write API is exposed.
3. Validate stable model label IDs, translations, phrase references, reviewer status, and provenance.
4. Deploy the compatible recognition model and vocabulary records together.
5. Set `ISL_VOCABULARY_VERSION` to the reviewed catalog version and restart the API.
6. Check the authenticated coverage endpoint and test with known, consented examples before enabling the flow for users.

The backend loads at most 10,000 verified entries per connection snapshot. This is a defensive bound, not a vocabulary-size performance claim. Large catalogs should use a separate immutable cache/index strategy and measured refresh policy before increasing the cap.

### Importing reviewed records

There is no bulk import API. Use an authenticated MongoDB Atlas Data Explorer or `mongosh` session with a restricted database account, select the configured application database, and insert reviewed records into `supported_signs`. Start with `insertOne` so existing records are never replaced. This schema-only example is deliberately unverified and is not a real sign:

```javascript
db.supported_signs.insertOne({
  sign_id: "REPLACE_WITH_REVIEWED_STABLE_ID",
  sign_name: "REPLACE_WITH_REVIEWED_NAME",
  sign_category: "REPLACE_WITH_REVIEWED_CATEGORY",
  description: "REPLACE_WITH_REVIEWER_APPROVED_DESCRIPTION",
  language: "isl",
  hand_configuration: null,
  movement_description: null,
  hand_orientation: null,
  dominant_hand: null,
  facial_expression: null,
  body_posture: null,
  animation_asset: null,
  synonyms: [],
  dataset_reference: "REPLACE_WITH_LICENSED_SOURCE_AND_PROVENANCE",
  verification_status: "unverified",
  vocabulary_version: null,
  translation_texts: {},
  compatible_model_versions: [],
  sequence_sign_ids: [],
  created_at: new Date(),
  updated_at: new Date()
});
```

Replace every placeholder using source material and qualified review; do not mark a record `verified` until its translations, version, provenance, and compatible model labels have been validated. Do not claim useful vocabulary coverage until the authenticated coverage endpoint reports it. Do not import this placeholder record as a usable entry.

## Feedback

User feedback is stored with `verification_status=pending_review`. It is not automatically used to change vocabulary records, model labels, training data, or model weights. A review workflow must check consent, licensing, data quality, and annotator agreement before any future use.

See [the language-engine guide](isl-language-engine.md) for response statuses, session behavior, API details, and test limitations.

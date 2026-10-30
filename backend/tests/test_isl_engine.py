from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.database.documents import SupportedSignDocument
from app.isl.interpreter import ISLSequenceInterpreter
from app.isl.vocabulary import ISLVocabulary
from app.services.gesture_classifier import ClassificationStatus, GesturePrediction

SESSION_ONE = UUID("00000000-0000-0000-0000-000000000001")
SESSION_TWO = UUID("00000000-0000-0000-0000-000000000002")
SEQUENCE_ID = UUID("00000000-0000-0000-0000-000000000003")
MODEL_VERSION = "fixture-model-v1"


def vocabulary_entry(
    sign_id: str,
    *,
    verified: bool = True,
    version: str = "fixture-v1",
    translations: dict[str, str] | None = None,
    sequence_sign_ids: list[str] | None = None,
) -> SupportedSignDocument:
    return SupportedSignDocument(
        sign_id=sign_id,
        sign_name=f"Fixture {sign_id}",
        sign_category="fixture",
        language="isl",
        verification_status="verified" if verified else "unverified",
        vocabulary_version=version,
        translation_texts=(
            translations
            if translations is not None
            else {"en": f"fixture translation {sign_id}"}
        ),
        compatible_model_versions=[MODEL_VERSION],
        sequence_sign_ids=sequence_sign_ids or [],
        created_at=datetime.now(timezone.utc),
    )


def prediction(
    label: str | None,
    *,
    status: ClassificationStatus = "classified",
    confidence: float | None = 0.95,
    model_version: str | None = MODEL_VERSION,
) -> GesturePrediction:
    return GesturePrediction(status, label, confidence, model_version)


def test_vocabulary_only_exposes_verified_entries_with_matching_version() -> None:
    vocabulary = ISLVocabulary(
        [
            vocabulary_entry("verified"),
            vocabulary_entry("unverified", verified=False),
            vocabulary_entry("stale", version="fixture-v0"),
        ],
        version="fixture-v1",
    )

    assert vocabulary.lookup("verified") is not None
    assert vocabulary.lookup("unverified") is None
    assert vocabulary.lookup("stale") is None
    assert vocabulary.sign_count == 1
    assert vocabulary.supported_languages == ["en"]


def test_verified_entries_require_translation_and_model_compatibility() -> None:
    with pytest.raises(ValueError, match="no translations"):
        ISLVocabulary(
            [vocabulary_entry("empty", translations={})],
            version="fixture-v1",
        )

    invalid_model = vocabulary_entry("no-model")
    invalid_model.compatible_model_versions = []
    with pytest.raises(ValueError, match="no compatible model versions"):
        ISLVocabulary([invalid_model], version="fixture-v1")


def test_unknown_low_confidence_and_incompatible_predictions_are_not_translated() -> None:
    vocabulary = ISLVocabulary(
        [vocabulary_entry("known")],
        version="fixture-v1",
    )
    interpreter = ISLSequenceInterpreter(vocabulary, confidence_threshold=0.75)

    unknown = interpreter.interpret(
        prediction(None, status="unknown", confidence=None),
        session_id=SESSION_ONE,
        sequence_id=SEQUENCE_ID,
    )
    low_confidence = interpreter.interpret(
        prediction(None, status="unknown", confidence=0.4),
        session_id=SESSION_ONE,
        sequence_id=SEQUENCE_ID,
    )
    unmapped = interpreter.interpret(
        prediction("unknown-label"),
        session_id=SESSION_ONE,
        sequence_id=SEQUENCE_ID,
    )
    incompatible = interpreter.interpret(
        prediction("known", model_version="unvalidated-model"),
        session_id=SESSION_ONE,
        sequence_id=SEQUENCE_ID,
    )

    assert unknown.status == "unknown_gesture"
    assert unknown.interpreted_text == ""
    assert low_confidence.status == "low_confidence"
    assert low_confidence.interpreted_text == ""
    assert unmapped.status == "unsupported"
    assert unmapped.interpreted_text == ""
    assert incompatible.status == "unsupported"
    assert incompatible.interpreted_text == ""


def test_repeated_predictions_are_filtered_and_verified_phrase_is_segmented() -> None:
    vocabulary = ISLVocabulary(
        [
            vocabulary_entry("first"),
            vocabulary_entry("second"),
            vocabulary_entry(
                "fixture-phrase",
                sequence_sign_ids=["first", "second"],
                translations={"en": "fixture phrase output"},
            ),
        ],
        version="fixture-v1",
    )
    interpreter = ISLSequenceInterpreter(vocabulary, confidence_threshold=0.75)

    first = interpreter.interpret(
        prediction("first"),
        session_id=SESSION_ONE,
        sequence_id=SEQUENCE_ID,
    )
    repeated = interpreter.interpret(
        prediction("first"),
        session_id=SESSION_ONE,
        sequence_id=SEQUENCE_ID,
    )
    phrase = interpreter.interpret(
        prediction("second"),
        session_id=SESSION_ONE,
        sequence_id=SEQUENCE_ID,
    )
    fresh_session = interpreter.interpret(
        prediction("first"),
        session_id=SESSION_TWO,
        sequence_id=SEQUENCE_ID,
    )

    assert first.interpreted_text == "fixture translation first"
    assert len(repeated.recognized_signs) == 1
    assert phrase.status == "success"
    assert phrase.translation_level == "phrase"
    assert phrase.interpreted_text == "fixture phrase output"
    assert [sign.sign_id for sign in fresh_session.recognized_signs] == ["first"]


def test_multiple_single_signs_do_not_claim_sentence_grammar() -> None:
    vocabulary = ISLVocabulary(
        [vocabulary_entry("first"), vocabulary_entry("second")],
        version="fixture-v1",
    )
    interpreter = ISLSequenceInterpreter(vocabulary, confidence_threshold=0.75)

    interpreter.interpret(
        prediction("first"),
        session_id=SESSION_ONE,
        sequence_id=SEQUENCE_ID,
    )
    result = interpreter.interpret(
        prediction("second"),
        session_id=SESSION_ONE,
        sequence_id=SEQUENCE_ID,
    )

    assert result.status == "partial"
    assert result.translation_level == "partial"
    assert result.interpreted_text == ""
    assert result.unsupported_segments[-1].reason == "no_verified_phrase_or_sentence_grammar"


def test_unconfigured_vocabulary_never_maps_model_labels() -> None:
    vocabulary = ISLVocabulary([vocabulary_entry("known")], version=None)
    interpreter = ISLSequenceInterpreter(vocabulary, confidence_threshold=0.75)

    result = interpreter.interpret(
        prediction("known"),
        session_id=SESSION_ONE,
        sequence_id=SEQUENCE_ID,
    )

    assert vocabulary.sign_count == 0
    assert result.status == "unsupported"
    assert result.vocabulary_version is None
    assert result.interpreted_text == ""

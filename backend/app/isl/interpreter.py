from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.isl.schemas import (
    ISLTranslationResponse,
    RecognizedSign,
    TranslationLevel,
    TranslationStatus,
    UnsupportedSegment,
)
from app.isl.vocabulary import ISLVocabulary, SupportedLanguage, VocabularyEntry
from app.services.gesture_classifier import GesturePrediction

MAX_SEQUENCE_SIGNS = 32


class ISLSequenceInterpreter:
    def __init__(
        self,
        vocabulary: ISLVocabulary,
        *,
        confidence_threshold: float,
        language: SupportedLanguage = "en",
    ) -> None:
        self._vocabulary = vocabulary
        self._confidence_threshold = confidence_threshold
        self._language = language
        self._session_id: UUID | None = None
        self._session_initialized = False
        self._model_version: str | None = None
        self._last_prediction_label: str | None = None
        self._recognized_signs: list[RecognizedSign] = []
        self._sign_ids: list[str] = []
        self._unsupported: list[UnsupportedSegment] = []

    def interpret(
        self,
        prediction: GesturePrediction,
        *,
        session_id: UUID | None,
        sequence_id: UUID,
        language: SupportedLanguage | None = None,
    ) -> ISLTranslationResponse:
        if self._session_initialized and (
            session_id != self._session_id
            or (language is not None and language != self._language)
            or prediction.model_version != self._model_version
        ):
            self.reset()
        self._session_initialized = True
        self._session_id = session_id
        self._model_version = prediction.model_version
        if language is not None:
            self._language = language
        status: TranslationStatus | None = None

        if prediction.status == "model_unavailable":
            self._last_prediction_label = None
            status = "unsupported"
            self._add_unsupported(None, "recognition_model_unavailable")
        elif prediction.status == "unknown":
            self._last_prediction_label = None
            status = (
                "low_confidence"
                if prediction.confidence is not None
                and prediction.confidence < self._confidence_threshold
                else "unknown_gesture"
            )
        elif (
            prediction.label is None
            or prediction.confidence is None
            or prediction.confidence < self._confidence_threshold
        ):
            self._last_prediction_label = None
            status = "low_confidence"
        elif prediction.label != self._last_prediction_label:
            self._last_prediction_label = prediction.label
            entry = self._vocabulary.lookup(prediction.label)
            if entry is None:
                status = "unsupported"
                self._add_unsupported(prediction.label, "sign_not_in_verified_vocabulary")
            elif not self._vocabulary.is_compatible(entry, prediction.model_version):
                status = "unsupported"
                self._add_unsupported(prediction.label, "model_version_not_verified_for_sign")
            else:
                translation = entry.translations.get(self._language)
                self._recognized_signs.append(
                    self._recognized_sign(entry, prediction.confidence, translation)
                )
                self._sign_ids.append(entry.sign_id)
                if len(self._recognized_signs) > MAX_SEQUENCE_SIGNS:
                    self._recognized_signs = self._recognized_signs[-MAX_SEQUENCE_SIGNS:]
                    self._sign_ids = self._sign_ids[-MAX_SEQUENCE_SIGNS:]
                    self._unsupported = [
                        UnsupportedSegment(reason="sequence_history_truncated")
                    ]

        interpreted_text, level, sequence_status, derived_unsupported = self._render_sequence(
            prediction.model_version
        )
        if status is None:
            status = sequence_status
        unsupported = [*self._unsupported, *derived_unsupported]
        if status == "success" and unsupported:
            status = "partial"

        confidence = prediction.confidence
        if confidence is not None and confidence < self._confidence_threshold:
            confidence = None
        response = ISLTranslationResponse(
            translation_id=uuid4(),
            status=status,
            session_id=session_id,
            sequence_id=sequence_id,
            recognized_signs=list(self._recognized_signs),
            interpreted_text=interpreted_text,
            language=self._language,
            confidence=confidence,
            translation_level=level,
            unsupported_segments=unsupported[:64],
            model_version=prediction.model_version,
            vocabulary_version=self._vocabulary.version,
            timestamp=datetime.now(timezone.utc),
        )
        return response

    def reset(self) -> None:
        self._session_id = None
        self._session_initialized = False
        self._model_version = None
        self._last_prediction_label = None
        self._recognized_signs.clear()
        self._sign_ids.clear()
        self._unsupported.clear()

    def _render_sequence(
        self,
        model_version: str | None,
    ) -> tuple[str, TranslationLevel, TranslationStatus, list[UnsupportedSegment]]:
        if self._unsupported:
            return "", "partial", "partial", []
        if not self._recognized_signs:
            return "", "partial", "unknown_gesture", []

        phrase = self._vocabulary.lookup_phrase(tuple(self._sign_ids))
        if (
            phrase is not None
            and self._vocabulary.is_compatible(phrase, model_version)
            and (text := phrase.translations.get(self._language)) is not None
        ):
            return text, "phrase", "success", []

        if len(self._recognized_signs) == 1:
            sign = self._recognized_signs[0]
            if sign.translation is not None:
                return sign.translation, "single_sign", "success", []
            return "", "partial", "partial", [
                UnsupportedSegment(
                    sign_id=sign.sign_id,
                    reason=f"translation_not_available_for_{self._language}",
                )
            ]

        return "", "partial", "partial", [
            UnsupportedSegment(reason="no_verified_phrase_or_sentence_grammar")
        ]

    def _add_unsupported(self, sign_id: str | None, reason: str) -> None:
        self._unsupported.append(UnsupportedSegment(sign_id=sign_id, reason=reason))
        if len(self._unsupported) > 64:
            self._unsupported = self._unsupported[-64:]

    @staticmethod
    def _recognized_sign(
        entry: VocabularyEntry,
        confidence: float,
        translation: str | None,
    ) -> RecognizedSign:
        return RecognizedSign(
            sign_id=entry.sign_id,
            sign_name=entry.sign_name,
            category=entry.category,
            confidence=confidence,
            translation=translation,
            hand_configuration=entry.hand_configuration,
            hand_movement=entry.hand_movement,
            hand_orientation=entry.hand_orientation,
            dominant_hand=entry.dominant_hand,
            facial_expression=entry.facial_expression,
            body_position=entry.body_position,
        )

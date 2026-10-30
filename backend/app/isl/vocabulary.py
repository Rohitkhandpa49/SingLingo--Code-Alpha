from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from app.database.documents import SupportedSignDocument

SupportedLanguage = Literal["en", "hi"]


@dataclass(frozen=True, slots=True)
class VocabularyEntry:
    sign_id: str
    sign_name: str
    category: str
    vocabulary_version: str
    translations: dict[SupportedLanguage, str]
    compatible_model_versions: frozenset[str]
    sequence_sign_ids: tuple[str, ...]
    hand_configuration: str | None
    hand_movement: str | None
    hand_orientation: str | None
    dominant_hand: str | None
    facial_expression: str | None
    body_position: str | None
    dataset_reference: str | None
    animation_asset: str | None


class ISLVocabulary:
    def __init__(
        self,
        documents: Iterable[SupportedSignDocument],
        *,
        version: str | None,
    ) -> None:
        self.version = version
        self._entries: dict[str, VocabularyEntry] = {}
        self._phrases: dict[tuple[str, ...], VocabularyEntry] = {}

        if version is None:
            return

        for document in documents:
            if (
                document.verification_status != "verified"
                or document.language != "isl"
                or document.vocabulary_version != version
            ):
                continue
            if not all(
                value.strip()
                for value in (document.sign_id, document.sign_name, document.sign_category)
            ):
                raise ValueError("Verified vocabulary identifiers and names cannot be blank")
            if not document.translation_texts:
                raise ValueError(
                    f"Verified vocabulary entry {document.sign_id!r} has no translations"
                )
            if not document.compatible_model_versions:
                raise ValueError(
                    f"Verified vocabulary entry {document.sign_id!r} has no compatible model versions"
                )
            if any(not text.strip() for text in document.translation_texts.values()):
                raise ValueError(
                    f"Verified vocabulary entry {document.sign_id!r} has an empty translation"
                )
            if any(not model_version.strip() for model_version in document.compatible_model_versions):
                raise ValueError(
                    f"Verified vocabulary entry {document.sign_id!r} has a blank model version"
                )
            if any(not sign_id.strip() for sign_id in document.sequence_sign_ids):
                raise ValueError(
                    f"Verified vocabulary entry {document.sign_id!r} has a blank phrase sign ID"
                )
            entry = VocabularyEntry(
                sign_id=document.sign_id,
                sign_name=document.sign_name,
                category=document.sign_category,
                vocabulary_version=version,
                translations=dict(document.translation_texts),
                compatible_model_versions=frozenset(document.compatible_model_versions),
                sequence_sign_ids=tuple(document.sequence_sign_ids),
                hand_configuration=document.hand_configuration,
                hand_movement=document.movement_description,
                hand_orientation=document.hand_orientation,
                dominant_hand=document.dominant_hand,
                facial_expression=document.facial_expression,
                body_position=document.body_posture,
                dataset_reference=document.dataset_reference,
                animation_asset=document.animation_asset,
            )
            if entry.sequence_sign_ids:
                if len(entry.sequence_sign_ids) < 2:
                    raise ValueError(
                        f"Verified phrase {document.sign_id!r} must contain at least two signs"
                    )
                if entry.sequence_sign_ids in self._phrases:
                    raise ValueError("Vocabulary contains a duplicate verified phrase")
                self._phrases[entry.sequence_sign_ids] = entry
            elif entry.sign_id in self._entries:
                raise ValueError(f"Vocabulary contains duplicate sign ID {entry.sign_id!r}")
            else:
                self._entries[entry.sign_id] = entry

        known_sign_ids = set(self._entries)
        for entry in self._phrases.values():
            if not set(entry.sequence_sign_ids).issubset(known_sign_ids):
                raise ValueError(
                    f"Verified phrase {entry.sign_id!r} references an unknown or unverified sign"
                )

    def lookup(self, sign_id: str) -> VocabularyEntry | None:
        return self._entries.get(sign_id)

    def lookup_phrase(self, sign_ids: tuple[str, ...]) -> VocabularyEntry | None:
        return self._phrases.get(sign_ids)

    def is_compatible(self, entry: VocabularyEntry, model_version: str | None) -> bool:
        return model_version is not None and model_version in entry.compatible_model_versions

    @property
    def sign_count(self) -> int:
        return len(self._entries)

    @property
    def phrase_count(self) -> int:
        return len(self._phrases)

    @property
    def supported_languages(self) -> list[SupportedLanguage]:
        languages = {
            language
            for entry in (*self._entries.values(), *self._phrases.values())
            for language in entry.translations
        }
        return sorted(languages)

    @property
    def entries(self) -> tuple[VocabularyEntry, ...]:
        return tuple(self._entries.values()) + tuple(self._phrases.values())

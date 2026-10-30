import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from app.isl.avatar_assets import (
    DEFAULT_AVATAR_ASSET_REGISTRY,
    AvatarAssetRegistry,
)
from app.isl.schemas import (
    ISLTextSequenceItem,
    ISLTextTranslationResponse,
    ISLTextUnsupportedSegment,
)
from app.isl.vocabulary import ISLVocabulary, SupportedLanguage, VocabularyEntry

MAX_INPUT_TOKENS = 62
MAX_OUTPUT_SIGNS = 24
WHITESPACE = re.compile(r"\s+")
TextTranslationStatus = Literal["success", "partial", "unsupported"]
TextTranslationLevel = Literal["single_sign", "phrase", "partial"]


@dataclass(frozen=True, slots=True)
class TextMatch:
    entry: VocabularyEntry
    start_token: int
    end_token: int
    sign_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WordToken:
    text: str
    start: int
    end: int


class ISLTextTranslator:
    def __init__(
        self,
        vocabulary: ISLVocabulary,
        *,
        avatar_assets: AvatarAssetRegistry = DEFAULT_AVATAR_ASSET_REGISTRY,
    ) -> None:
        self._vocabulary = vocabulary
        self._avatar_assets = avatar_assets

    def translate(
        self,
        text: str,
        *,
        language: Literal["auto", "en", "hi"],
    ) -> ISLTextTranslationResponse:
        normalized = WHITESPACE.sub(" ", unicodedata.normalize("NFC", text)).strip()
        resolved_language = self._resolve_language(normalized, language)
        if resolved_language is None:
            reason = (
                "mixed_script_requires_language_selection"
                if self._has_latin(normalized) and self._has_devanagari(normalized)
                else "language_not_detected"
            )
            unsupported = (
                [
                    ISLTextUnsupportedSegment(
                        start_index=0,
                        end_index=len(normalized),
                        text=normalized,
                        reason=reason,
                    )
                ]
                if normalized
                else []
            )
            return self._response(
                text=text,
                normalized=normalized,
                language=None,
                sequence=[],
                unsupported=unsupported,
                status="unsupported",
                level="partial",
            )

        words = self._words(normalized)
        if not words:
            unsupported = (
                [
                    ISLTextUnsupportedSegment(
                        start_index=0,
                        end_index=len(normalized),
                        text=normalized,
                        reason="no_word_tokens",
                    )
                ]
                if normalized
                else []
            )
            return self._response(
                text=text,
                normalized=normalized,
                language=resolved_language,
                sequence=[],
                unsupported=unsupported,
                status="unsupported",
                level="partial",
            )

        candidates = self._candidate_map(resolved_language)
        token_limit = min(len(words), MAX_INPUT_TOKENS)
        bounded_words = words[:token_limit]
        sequence: list[ISLTextSequenceItem] = []
        unsupported: list[ISLTextUnsupportedSegment] = []
        matches: list[TextMatch] = []
        token_index = 0

        while token_index < token_limit:
            match, ambiguous_length = self._match_at(
                bounded_words,
                token_index,
                candidates,
            )
            if match is not None:
                matches.append(match)
                matched_text = normalized[
                    words[match.start_token].start : words[match.end_token - 1].end
                ]
                sequence_limit_reached = False
                for sign_id in match.sign_ids:
                    sign = self._vocabulary.lookup(sign_id)
                    if sign is None:
                        continue
                    if len(sequence) >= MAX_OUTPUT_SIGNS:
                        self._add_unsupported(
                            unsupported,
                            normalized,
                            words[match.start_token].start,
                            words[-1].end,
                            "sequence_limit_exceeded",
                        )
                        token_index = token_limit
                        sequence_limit_reached = True
                        break
                    asset = self._avatar_assets.resolve(sign.sign_id, sign.animation_asset)
                    sequence.append(
                        ISLTextSequenceItem(
                            sign_id=sign.sign_id,
                            sign_name=sign.sign_name,
                            matched_text=matched_text,
                            animation_asset=asset.path if asset else None,
                            animation_clip=asset.clip_name if asset else None,
                        )
                    )
                if not sequence_limit_reached:
                    token_index = match.end_token
                continue
            if ambiguous_length:
                end = min(token_index + ambiguous_length, token_limit)
                self._add_unsupported(
                    unsupported,
                    normalized,
                    words[token_index].start,
                    words[end - 1].end,
                    "ambiguous_verified_mapping",
                )
                token_index = end
                continue

            start = token_index
            token_index += 1
            while token_index < token_limit:
                next_match, next_ambiguous_length = self._match_at(
                    bounded_words,
                    token_index,
                    candidates,
                )
                if next_match is not None or next_ambiguous_length:
                    break
                token_index += 1
            self._add_unsupported(
                unsupported,
                normalized,
                words[start].start,
                words[token_index - 1].end,
                "no_verified_mapping",
            )

        if len(words) > MAX_INPUT_TOKENS:
            self._add_unsupported(
                unsupported,
                normalized,
                words[MAX_INPUT_TOKENS].start,
                len(normalized),
                "input_token_limit_exceeded",
            )

        if (
            not unsupported
            and len(matches) > 1
        ):
            self._add_unsupported(
                unsupported,
                normalized,
                0,
                len(normalized),
                "sentence_grammar_unavailable",
            )

        status: TextTranslationStatus = (
            "success" if sequence and not unsupported else "partial" if sequence else "unsupported"
        )
        level: TextTranslationLevel = (
            "single_sign"
            if len(sequence) == 1
            else "phrase"
            if sequence and not unsupported
            else "partial"
        )
        return self._response(
            text=text,
            normalized=normalized,
            language=resolved_language,
            sequence=sequence,
            unsupported=unsupported,
            status=status,
            level=level,
        )

    def _candidate_map(
        self,
        language: SupportedLanguage,
    ) -> dict[tuple[str, ...], list[tuple[VocabularyEntry, tuple[str, ...]]]]:
        candidates: dict[
            tuple[str, ...],
            list[tuple[VocabularyEntry, tuple[str, ...]]],
        ] = {}
        for entry in self._vocabulary.entries:
            translated = entry.translations.get(language)
            if translated is None:
                continue
            key = tuple(token.text.casefold() for token in self._words(translated))
            if not key:
                continue
            sign_ids = entry.sequence_sign_ids or (entry.sign_id,)
            candidates.setdefault(key, []).append((entry, sign_ids))
        return candidates

    @staticmethod
    def _match_at(
        words: list[WordToken],
        start: int,
        candidates: dict[tuple[str, ...], list[tuple[VocabularyEntry, tuple[str, ...]]]],
    ) -> tuple[TextMatch | None, int]:
        for key_length in range(min(MAX_INPUT_TOKENS, len(words) - start), 0, -1):
            key = tuple(
                words[index].text.casefold()
                for index in range(start, start + key_length)
            )
            entries = candidates.get(key)
            if entries is None:
                continue
            if len(entries) != 1:
                return None, key_length
            entry, sign_ids = entries[0]
            return TextMatch(entry, start, start + key_length, sign_ids), 0
        return None, 0

    @staticmethod
    def _words(text: str) -> list[WordToken]:
        tokens: list[WordToken] = []
        token_start: int | None = None
        for index, character in enumerate(text):
            category = unicodedata.category(character)
            is_word_character = category[0] in {"L", "M", "N"} or character == "_"
            if is_word_character and token_start is None:
                token_start = index
            elif not is_word_character and token_start is not None:
                tokens.append(WordToken(text[token_start:index], token_start, index))
                token_start = None
        if token_start is not None:
            tokens.append(WordToken(text[token_start:], token_start, len(text)))
        return tokens

    @staticmethod
    def _resolve_language(text: str, language: str) -> SupportedLanguage | None:
        if language in {"en", "hi"}:
            return language
        has_latin = ISLTextTranslator._has_latin(text)
        has_devanagari = ISLTextTranslator._has_devanagari(text)
        if has_latin == has_devanagari:
            return None
        return "hi" if has_devanagari else "en"

    @staticmethod
    def _has_latin(text: str) -> bool:
        return re.search(r"[A-Za-z]", text) is not None

    @staticmethod
    def _has_devanagari(text: str) -> bool:
        return re.search(r"[\u0900-\u097f]", text) is not None

    @staticmethod
    def _add_unsupported(
        unsupported: list[ISLTextUnsupportedSegment],
        normalized: str,
        start: int,
        end: int,
        reason: str,
    ) -> None:
        if len(unsupported) >= 64 or end <= start:
            return
        unsupported.append(
            ISLTextUnsupportedSegment(
                start_index=start,
                end_index=end,
                text=normalized[start:end],
                reason=reason,
            )
        )

    def _response(
        self,
        *,
        text: str,
        normalized: str,
        language: SupportedLanguage | None,
        sequence: list[ISLTextSequenceItem],
        unsupported: list[ISLTextUnsupportedSegment],
        status: TextTranslationStatus,
        level: TextTranslationLevel,
    ) -> ISLTextTranslationResponse:
        return ISLTextTranslationResponse(
            translation_id=uuid4(),
            status=status,
            source_text=text,
            normalized_text=normalized,
            language=language,
            sequence=sequence,
            unsupported_segments=unsupported,
            translation_level=level,
            vocabulary_version=self._vocabulary.version,
            sentence_grammar_available=False,
            timestamp=datetime.now(timezone.utc),
        )

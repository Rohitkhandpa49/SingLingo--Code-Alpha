from datetime import datetime, timezone

import pytest

from app.database.documents import SupportedSignDocument
from app.isl.avatar_assets import (
    AvatarAnimationAsset,
    AvatarAssetRegistry,
)
from app.isl.text_translator import ISLTextTranslator
from app.isl.vocabulary import ISLVocabulary

MODEL_VERSION = "fixture-model-v1"


def vocabulary_document(
    sign_id: str,
    translation: str,
    *,
    language: str = "en",
    sequence_sign_ids: list[str] | None = None,
    animation_asset: str | None = None,
    verified: bool = True,
) -> SupportedSignDocument:
    return SupportedSignDocument(
        sign_id=sign_id,
        sign_name=f"Verified {sign_id}",
        sign_category="fixture",
        language="isl",
        verification_status="verified" if verified else "unverified",
        vocabulary_version="fixture-v1",
        translation_texts={language: translation},
        compatible_model_versions=[MODEL_VERSION],
        sequence_sign_ids=sequence_sign_ids or [],
        animation_asset=animation_asset,
        created_at=datetime.now(timezone.utc),
    )


def make_translator(
    documents: list[SupportedSignDocument],
    *,
    assets: AvatarAssetRegistry | None = None,
) -> ISLTextTranslator:
    return ISLTextTranslator(
        ISLVocabulary(documents, version="fixture-v1"),
        avatar_assets=assets or AvatarAssetRegistry(),
    )


def test_maps_only_exact_verified_single_sign_and_phrase_entries() -> None:
    translator = make_translator(
        [
            vocabulary_document("hello", "hello"),
            vocabulary_document("thanks", "thank you"),
            vocabulary_document(
                "greeting",
                "good morning",
                sequence_sign_ids=["hello", "thanks"],
            ),
            vocabulary_document("unreviewed", "secret word", verified=False),
        ]
    )

    single = translator.translate("  HELLO!  ", language="auto")
    phrase = translator.translate("GOOD morning", language="en")
    unsupported = translator.translate("secret word", language="en")

    assert single.status == "success"
    assert single.language == "en"
    assert [item.sign_id for item in single.sequence] == ["hello"]
    assert phrase.status == "success"
    assert phrase.translation_level == "phrase"
    assert [item.sign_id for item in phrase.sequence] == ["hello", "thanks"]
    assert unsupported.status == "unsupported"
    assert unsupported.sequence == []
    assert unsupported.unsupported_segments[0].reason == "no_verified_mapping"


def test_normalizes_devanagari_and_detects_hindi_by_script() -> None:
    translator = make_translator(
        [vocabulary_document("hello-hi", "नमस्ते", language="hi")]
    )

    result = translator.translate("  नमस्ते। ", language="auto")

    assert result.normalized_text == "नमस्ते।"
    assert result.language == "hi"
    assert result.status == "success"
    assert result.sequence[0].matched_text == "नमस्ते"


def test_reports_mixed_script_unknown_text_and_ungrammatical_word_sequences() -> None:
    translator = make_translator(
        [
            vocabulary_document("hello", "hello"),
            vocabulary_document("thanks", "thanks"),
        ]
    )

    mixed = translator.translate("hello नमस्ते", language="auto")
    partial = translator.translate("hello mystery", language="en")
    word_sequence = translator.translate("hello thanks", language="en")

    assert mixed.status == "unsupported"
    assert mixed.unsupported_segments[0].reason == "mixed_script_requires_language_selection"
    assert partial.status == "partial"
    assert partial.sequence[0].sign_id == "hello"
    assert partial.unsupported_segments[0].text == "mystery"
    assert word_sequence.status == "partial"
    assert word_sequence.unsupported_segments[0].reason == "sentence_grammar_unavailable"
    assert word_sequence.sentence_grammar_available is False


def test_ambiguous_mappings_are_not_chosen_arbitrarily() -> None:
    translator = make_translator(
        [
            vocabulary_document("first", "hello"),
            vocabulary_document("second", "hello"),
        ]
    )

    result = translator.translate("hello", language="en")

    assert result.status == "unsupported"
    assert result.sequence == []
    assert result.unsupported_segments[0].reason == "ambiguous_verified_mapping"


def test_only_registered_safe_avatar_assets_are_returned() -> None:
    asset = AvatarAnimationAsset(
        path="/assets/signs/hello.glb",
        clip_name="Hello",
    )
    translator = make_translator(
        [
            vocabulary_document(
                "hello",
                "hello",
                animation_asset="https://invalid.example/hello.glb",
            )
        ],
        assets=AvatarAssetRegistry({"hello": asset}),
    )

    result = translator.translate("hello", language="en")

    assert result.sequence[0].animation_asset is None
    assert result.sequence[0].animation_clip is None
    assert AvatarAssetRegistry({"hello": asset}).resolve(
        "hello",
        "/assets/signs/hello.glb",
    ) == asset


@pytest.mark.parametrize(
    ("sign_id", "path", "clip_name"),
    [
        ("../hello", "/assets/signs/hello.glb", "Hello"),
        ("hello", "https://invalid.example/hello.glb", "Hello"),
        ("hello", "/assets/signs/other.glb", "Hello"),
        ("hello", "/assets/signs/hello.glb", ""),
    ],
)
def test_rejects_unsafe_avatar_registry_entries(
    sign_id: str,
    path: str,
    clip_name: str,
) -> None:
    with pytest.raises(ValueError, match="safe sign IDs"):
        AvatarAssetRegistry(
            {sign_id: AvatarAnimationAsset(path=path, clip_name=clip_name)}
        )

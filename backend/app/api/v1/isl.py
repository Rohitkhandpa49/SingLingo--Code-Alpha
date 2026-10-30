from fastapi import APIRouter, Depends, HTTPException, Request, status
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.database.repositories.documents import SupportedSignsRepository
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_database
from app.isl.schemas import (
    ISLTextTranslationRequest,
    ISLTextTranslationResponse,
    ISLVocabularyCoverageResponse,
    ISLVocabularyResponse,
)
from app.isl.text_translator import ISLTextTranslator
from app.isl.vocabulary import ISLVocabulary
from app.database.repositories.users import UserRecord

router = APIRouter(prefix="/isl", tags=["ISL vocabulary"])


async def load_vocabulary(
    database: AsyncDatabase,
    settings: Settings,
) -> ISLVocabulary:
    documents = await SupportedSignsRepository(database).list_verified_for_version(
        settings.isl_vocabulary_version
    )
    return ISLVocabulary(documents, version=settings.isl_vocabulary_version)


@router.get(
    "/vocabulary/coverage",
    response_model=ISLVocabularyCoverageResponse,
)
async def vocabulary_coverage(
    database: AsyncDatabase = Depends(get_database),
    settings: Settings = Depends(get_settings),
    _user: UserRecord = Depends(get_current_user),
) -> ISLVocabularyCoverageResponse:
    vocabulary = await load_vocabulary(database, settings)
    return ISLVocabularyCoverageResponse(
        vocabulary_version=vocabulary.version,
        verified_sign_count=vocabulary.sign_count,
        verified_phrase_count=vocabulary.phrase_count,
        supported_languages=vocabulary.supported_languages,
        sentence_grammar_available=False,
    )


@router.get(
    "/vocabulary/{sign_id}",
    response_model=ISLVocabularyResponse,
)
async def vocabulary_entry(
    sign_id: str,
    database: AsyncDatabase = Depends(get_database),
    settings: Settings = Depends(get_settings),
    _user: UserRecord = Depends(get_current_user),
) -> ISLVocabularyResponse:
    vocabulary = await load_vocabulary(database, settings)
    entry = vocabulary.lookup(sign_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No verified ISL vocabulary entry was found",
        )
    return ISLVocabularyResponse(
        sign_id=entry.sign_id,
        sign_name=entry.sign_name,
        category=entry.category,
        translations=entry.translations,
        vocabulary_version=entry.vocabulary_version,
        compatible_model_versions=sorted(entry.compatible_model_versions),
        hand_configuration=entry.hand_configuration,
        hand_movement=entry.hand_movement,
        hand_orientation=entry.hand_orientation,
        dominant_hand=entry.dominant_hand,
        facial_expression=entry.facial_expression,
        body_position=entry.body_position,
        dataset_reference=entry.dataset_reference,
    )


@router.post(
    "/translate-text",
    response_model=ISLTextTranslationResponse,
)
@limiter.limit("30/minute")
async def translate_text_to_signs(
    request: Request,
    payload: ISLTextTranslationRequest,
    database: AsyncDatabase = Depends(get_database),
    settings: Settings = Depends(get_settings),
    _user: UserRecord = Depends(get_current_user),
) -> ISLTextTranslationResponse:
    vocabulary = await load_vocabulary(database, settings)
    return ISLTextTranslator(vocabulary).translate(
        payload.text,
        language=payload.language,
    )

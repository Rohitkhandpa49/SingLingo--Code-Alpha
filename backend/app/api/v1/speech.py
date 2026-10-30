import logging
from functools import partial
from typing import Literal
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.database.repositories.users import UserRecord
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_database
from app.services.speech.audio_preprocessor import AudioValidationError
from app.services.speech.schemas import SpeechTranscriptionResponse
from app.services.speech.service import (
    SpeechRecognitionService,
    SpeechServiceBusy,
    UnsupportedSpeechLanguage,
)
from app.services.speech.whisper_provider import (
    SpeechProviderError,
    SpeechProviderUnavailable,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/speech", tags=["speech processing"])


@router.post(
    "/transcribe",
    response_model=SpeechTranscriptionResponse,
)
@limiter.limit("6/minute")
async def transcribe_audio(
    request: Request,
    audio: UploadFile = File(...),
    language: Literal["auto", "en", "hi"] = Form(default="auto"),
    session_id: UUID | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    _database: AsyncDatabase = Depends(get_database),
    _user: UserRecord = Depends(get_current_user),
) -> SpeechTranscriptionResponse:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            request_size = int(content_length)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request size",
            ) from None
        if request_size > settings.speech_max_audio_bytes + 65_536:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Audio exceeds the configured size limit",
            )

    try:
        audio_bytes = await audio.read(settings.speech_max_audio_bytes + 1)
    finally:
        await audio.close()
    if len(audio_bytes) > settings.speech_max_audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio exceeds the configured size limit",
        )

    service: SpeechRecognitionService = request.app.state.speech_service
    try:
        return await anyio.to_thread.run_sync(
            partial(
                service.transcribe,
                audio_bytes,
                content_type=audio.content_type or "",
                language=language,
                session_id=session_id,
            )
        )
    except AudioValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from None
    except UnsupportedSpeechLanguage as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from None
    except SpeechServiceBusy:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Speech recognition is busy. Try again shortly.",
        ) from None
    except SpeechProviderUnavailable as error:
        logger.warning(
            "Speech recognition is unavailable",
            extra={"error_type": error.__class__.__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech recognition is not configured or could not start",
        ) from None
    except SpeechProviderError as error:
        logger.error(
            "Speech recognition failed",
            extra={"error_type": error.__class__.__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech recognition is temporarily unavailable",
        ) from None


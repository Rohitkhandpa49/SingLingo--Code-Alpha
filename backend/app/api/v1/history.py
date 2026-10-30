from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pymongo.asynchronous.database import AsyncDatabase

from app.database.repositories.history import HistoryRecord, HistoryRepository
from app.database.repositories.users import UserRecord
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_database
from app.schemas.history import (
    HistoryCreateRequest,
    HistoryListResponse,
    HistoryResponse,
)

router = APIRouter(prefix="/history", tags=["translation history"])


def to_history_response(record: HistoryRecord) -> HistoryResponse:
    return HistoryResponse(
        id=str(record.id),
        direction=record.direction,
        source_language=record.source_language,
        target_language=record.target_language,
        input_text=record.input_text,
        output_text=record.output_text,
        confidence=record.confidence,
        created_at=record.created_at,
    )


@router.post("", response_model=HistoryResponse, status_code=status.HTTP_201_CREATED)
async def create_history_entry(
    payload: HistoryCreateRequest,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    user: UserRecord = Depends(get_current_user),
) -> HistoryResponse:
    record = await HistoryRepository(database).create(
        user.id,
        direction=payload.direction,
        source_language=payload.source_language,
        target_language=payload.target_language,
        input_text=payload.input_text,
        output_text=payload.output_text,
        confidence=payload.confidence,
    )
    return to_history_response(record)


@router.get("", response_model=HistoryListResponse)
async def list_history(
    search: str | None = Query(default=None, max_length=100),
    language: str | None = Query(default=None, pattern="^(isl|hi|en)$"),
    created_after: datetime | None = Query(default=None),
    created_before: datetime | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0, le=1_000_000),
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    user: UserRecord = Depends(get_current_user),
) -> HistoryListResponse:
    if created_after is not None and created_before is not None and created_after > created_before:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="created_after must be earlier than or equal to created_before",
        )
    records = await HistoryRepository(database).list_for_user(
        user.id,
        search=search,
        language=language,
        created_after=created_after,
        created_before=created_before,
        limit=limit,
        skip=skip,
    )
    return HistoryListResponse(
        items=[to_history_response(record) for record in records],
        limit=limit,
        skip=skip,
    )


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(
    entry_id: str,
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    user: UserRecord = Depends(get_current_user),
) -> Response:
    try:
        object_id = ObjectId(entry_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation history entry was not found",
        ) from None

    deleted = await HistoryRepository(database).delete_for_user(object_id, user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation history entry was not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

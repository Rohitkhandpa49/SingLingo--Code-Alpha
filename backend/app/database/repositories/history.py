import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from pymongo import DESCENDING
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pydantic import ValidationError

from app.core.time import as_utc
from app.database.documents import HistoryDocument, StoredDocumentError


@dataclass(frozen=True, slots=True)
class HistoryRecord:
    id: ObjectId
    direction: str
    source_language: str
    target_language: str
    input_text: str
    output_text: str
    confidence: float | None
    created_at: datetime


class HistoryRepository:
    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        *,
        retention_days: int | None = None,
    ) -> None:
        if retention_days is not None and retention_days < 1:
            raise ValueError("retention_days must be positive")
        self._retention_days = retention_days
        self._collection: AsyncCollection[dict[str, Any]] = database["translation_history"]

    async def create(
        self,
        user_id: ObjectId,
        *,
        direction: str,
        source_language: str,
        target_language: str,
        input_text: str,
        output_text: str,
        confidence: float | None,
    ) -> HistoryRecord:
        created_at = datetime.now(timezone.utc)
        document = HistoryDocument(
            user_id=user_id,
            direction=direction,
            source_language=source_language,
            target_language=target_language,
            input_text=input_text,
            output_text=output_text,
            confidence=confidence,
            created_at=created_at,
        )
        result = await self._collection.insert_one(
            document.model_dump(by_alias=True, exclude_none=True)
        )
        return HistoryRecord(
            id=result.inserted_id,
            direction=direction,
            source_language=source_language,
            target_language=target_language,
            input_text=input_text,
            output_text=output_text,
            confidence=confidence,
            created_at=created_at,
        )

    async def list_for_user(
        self,
        user_id: ObjectId,
        *,
        search: str | None,
        language: str | None,
        created_after: datetime | None,
        created_before: datetime | None,
        limit: int,
        skip: int,
    ) -> list[HistoryRecord]:
        if not 1 <= limit <= 100 or not 0 <= skip <= 1_000_000:
            raise ValueError("History pagination is outside the supported range")
        conditions: list[dict[str, Any]] = [{"user_id": user_id}]
        if search:
            escaped_search = re.escape(search.strip())
            conditions.append(
                {
                    "$or": [
                        {"input_text": {"$regex": escaped_search, "$options": "i"}},
                        {"output_text": {"$regex": escaped_search, "$options": "i"}},
                    ]
                }
            )
        if language:
            conditions.append(
                {
                    "$or": [
                        {"source_language": language},
                        {"target_language": language},
                    ]
                }
            )
        created_at: dict[str, datetime] = {}
        if created_after is not None:
            created_at["$gte"] = created_after
        if created_before is not None:
            created_at["$lte"] = created_before
        if created_at:
            conditions.append({"created_at": created_at})
        query = conditions[0] if len(conditions) == 1 else {"$and": conditions}
        cursor = (
            self._collection.find(query)
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )
        documents = await cursor.to_list(length=limit)
        return [self._to_record(document) for document in documents]

    async def delete_for_user(self, entry_id: ObjectId, user_id: ObjectId) -> bool:
        result = await self._collection.delete_one({"_id": entry_id, "user_id": user_id})
        return result.deleted_count == 1

    async def aggregate_counts_by_direction(self, user_id: ObjectId) -> list[dict[str, Any]]:
        cursor = self._collection.aggregate(
            [
                {"$match": {"user_id": user_id}},
                {
                    "$group": {
                        "_id": "$direction",
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        )
        return await cursor.to_list(length=10)

    async def purge_expired(self, *, dry_run: bool = True) -> int:
        if self._retention_days is None:
            raise RuntimeError("History retention is not configured")
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        query = {"created_at": {"$lt": cutoff}}
        if dry_run:
            return await self._collection.count_documents(query)
        result = await self._collection.delete_many(query)
        return result.deleted_count

    @staticmethod
    def _to_record(document: dict[str, Any]) -> HistoryRecord:
        try:
            stored = HistoryDocument.model_validate(document)
        except ValidationError as error:
            raise StoredDocumentError("translation_history") from error
        if stored.id is None:
            raise StoredDocumentError("translation_history")
        return HistoryRecord(
            id=stored.id,
            direction=stored.direction,
            source_language=stored.source_language,
            target_language=stored.target_language,
            input_text=stored.input_text,
            output_text=stored.output_text,
            confidence=stored.confidence,
            created_at=as_utc(stored.created_at),
        )

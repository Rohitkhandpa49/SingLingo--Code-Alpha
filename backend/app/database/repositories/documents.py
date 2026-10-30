import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

from bson import ObjectId
from pydantic import ValidationError
from pymongo import DESCENDING, ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection

from app.database.connection import Database
from app.database.documents import (
    AudioEventDocument,
    ConversationDocument,
    FeedbackDocument,
    ModelVersionDocument,
    MongoDocument,
    NotificationDocument,
    StoredDocumentError,
    SupportedSignDocument,
    UserPreferenceDocument,
)

DocumentT = TypeVar("DocumentT", bound=MongoDocument)
MAX_PAGE_SIZE = 100
MAX_SKIP = 1_000_000
MAX_SEARCH_LENGTH = 100
MAX_VOCABULARY_ENTRIES = 10_000


@dataclass(frozen=True, slots=True)
class RepositoryPage(Generic[DocumentT]):
    items: list[DocumentT]
    limit: int
    skip: int


class MongoRepository(Generic[DocumentT]):
    def __init__(
        self,
        database: Database,
        collection_name: str,
        document_type: type[DocumentT],
        *,
        filter_fields: frozenset[str],
        update_fields: frozenset[str],
        sort_fields: frozenset[str],
        search_fields: frozenset[str] = frozenset(),
    ) -> None:
        self.collection_name = collection_name
        self.document_type = document_type
        self.filter_fields = filter_fields
        self.update_fields = update_fields
        self.sort_fields = sort_fields
        self.search_fields = search_fields
        self._collection: AsyncCollection[dict[str, Any]] = database[collection_name]

    async def create(self, document: DocumentT) -> DocumentT:
        validated = self.document_type.model_validate(document)
        payload = validated.model_dump(by_alias=True, exclude_none=True)
        result = await self._collection.insert_one(payload)
        return validated.model_copy(update={"id": result.inserted_id})

    async def get_by_id(self, document_id: ObjectId) -> DocumentT | None:
        document = await self._collection.find_one({"_id": document_id})
        return self._validate_stored(document) if document is not None else None

    async def update_by_id(
        self,
        document_id: ObjectId,
        changes: Mapping[str, Any],
    ) -> DocumentT | None:
        invalid_fields = set(changes) - self.update_fields
        if invalid_fields:
            raise ValueError(f"Fields cannot be updated in {self.collection_name}")
        if not changes:
            raise ValueError("At least one update field is required")

        current = await self._collection.find_one({"_id": document_id})
        if current is None:
            return None
        self._validate_stored(current)
        try:
            candidate = self.document_type.model_validate({**current, **changes})
        except ValidationError as error:
            raise ValueError(f"Update is invalid for {self.collection_name}") from error
        validated_changes = {
            field: getattr(candidate, field)
            for field in changes
        }
        updated = await self._collection.find_one_and_update(
            {"_id": document_id},
            {"$set": validated_changes},
            return_document=ReturnDocument.AFTER,
        )
        return self._validate_stored(updated) if updated is not None else None

    async def delete_by_id(self, document_id: ObjectId) -> bool:
        result = await self._collection.delete_one({"_id": document_id})
        return result.deleted_count == 1

    async def list_page(
        self,
        *,
        filters: Mapping[str, Any] | None = None,
        search: str | None = None,
        limit: int = 20,
        skip: int = 0,
        sort_field: str = "created_at",
        descending: bool = True,
    ) -> RepositoryPage[DocumentT]:
        if not 1 <= limit <= MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}")
        if not 0 <= skip <= MAX_SKIP:
            raise ValueError(f"skip must be between 0 and {MAX_SKIP}")
        if sort_field not in self.sort_fields:
            raise ValueError(f"Unsupported sort field for {self.collection_name}")

        query = dict(filters or {})
        if set(query) - self.filter_fields:
            raise ValueError(f"Unsupported filter for {self.collection_name}")
        if search is not None:
            term = search.strip()
            if not term or len(term) > MAX_SEARCH_LENGTH or not self.search_fields:
                raise ValueError("Search term is invalid or unsupported")
            expression = {"$regex": re.escape(term), "$options": "i"}
            query["$or"] = [
                {field: expression}
                for field in sorted(self.search_fields)
            ]

        direction = DESCENDING if descending else 1
        cursor = (
            self._collection.find(query)
            .sort(sort_field, direction)
            .skip(skip)
            .limit(limit)
        )
        documents = await cursor.to_list(length=limit)
        return RepositoryPage(
            items=[self._validate_stored(document) for document in documents],
            limit=limit,
            skip=skip,
        )

    async def aggregate(
        self,
        pipeline: Sequence[Mapping[str, Any]],
        *,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        if not 1 <= max_results <= MAX_PAGE_SIZE:
            raise ValueError(f"max_results must be between 1 and {MAX_PAGE_SIZE}")
        cursor = self._collection.aggregate(list(pipeline))
        return await cursor.to_list(length=max_results)

    def _validate_stored(self, document: Mapping[str, Any]) -> DocumentT:
        try:
            return self.document_type.model_validate(document)
        except ValidationError as error:
            raise StoredDocumentError(self.collection_name) from error


class SupportedSignsRepository(MongoRepository[SupportedSignDocument]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database,
            "supported_signs",
            SupportedSignDocument,
            filter_fields=frozenset(
                {"language", "sign_category", "verification_status", "vocabulary_version"}
            ),
            update_fields=frozenset(
                {
                    "sign_name",
                    "sign_category",
                    "description",
                    "language",
                    "hand_configuration",
                    "movement_description",
                    "hand_orientation",
                    "dominant_hand",
                    "facial_expression",
                    "body_posture",
                    "animation_asset",
                    "synonyms",
                    "dataset_reference",
                    "verification_status",
                    "vocabulary_version",
                    "translation_texts",
                    "compatible_model_versions",
                    "sequence_sign_ids",
                    "updated_at",
                }
            ),
            sort_fields=frozenset({"created_at", "sign_name", "sign_id"}),
            search_fields=frozenset({"sign_name", "description", "synonyms"}),
        )

    async def list_verified_for_version(
        self,
        vocabulary_version: str | None,
    ) -> list[SupportedSignDocument]:
        if vocabulary_version is None:
            return []
        cursor = self._collection.find(
            {
                "language": "isl",
                "verification_status": "verified",
                "vocabulary_version": vocabulary_version,
            }
        ).limit(MAX_VOCABULARY_ENTRIES + 1)
        documents = await cursor.to_list(length=MAX_VOCABULARY_ENTRIES + 1)
        if len(documents) > MAX_VOCABULARY_ENTRIES:
            raise RuntimeError("The configured ISL vocabulary exceeds its safe size limit")
        return [self._validate_stored(document) for document in documents]


class ConversationRepository(MongoRepository[ConversationDocument]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database,
            "conversations",
            ConversationDocument,
            filter_fields=frozenset({"conversation_status", "participants"}),
            update_fields=frozenset(
                {"participants", "conversation_status", "preferred_languages", "ended_at"}
            ),
            sort_fields=frozenset({"started_at", "conversation_id"}),
        )

    async def get_by_conversation_id(self, conversation_id: str) -> ConversationDocument | None:
        document = await self._collection.find_one({"conversation_id": conversation_id})
        return self._validate_stored(document) if document is not None else None

    async def list_for_participant(
        self,
        user_id: ObjectId,
        *,
        limit: int = 20,
        skip: int = 0,
    ) -> RepositoryPage[ConversationDocument]:
        return await self.list_page(
            filters={"participants": user_id},
            limit=limit,
            skip=skip,
            sort_field="started_at",
        )


class NotificationRepository(MongoRepository[NotificationDocument]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database,
            "notifications",
            NotificationDocument,
            filter_fields=frozenset(
                {"user_id", "read_status", "priority", "notification_type"}
            ),
            update_fields=frozenset({"read_status"}),
            sort_fields=frozenset({"created_at", "priority"}),
        )

    async def list_for_user(
        self,
        user_id: ObjectId,
        *,
        read_status: bool | None = None,
        limit: int = 20,
        skip: int = 0,
    ) -> RepositoryPage[NotificationDocument]:
        filters: dict[str, Any] = {"user_id": user_id}
        if read_status is not None:
            filters["read_status"] = read_status
        return await self.list_page(filters=filters, limit=limit, skip=skip)

    async def mark_read(self, notification_id: ObjectId, user_id: ObjectId) -> bool:
        result = await self._collection.update_one(
            {"_id": notification_id, "user_id": user_id},
            {"$set": {"read_status": True}},
        )
        return result.matched_count == 1

    async def delete_for_user(self, notification_id: ObjectId, user_id: ObjectId) -> bool:
        result = await self._collection.delete_one(
            {"_id": notification_id, "user_id": user_id}
        )
        return result.deleted_count == 1


class AudioEventRepository(MongoRepository[AudioEventDocument]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database,
            "audio_events",
            AudioEventDocument,
            filter_fields=frozenset({"user_id", "severity", "event_type"}),
            update_fields=frozenset(),
            sort_fields=frozenset({"created_at", "severity"}),
        )

    async def list_for_user(
        self, user_id: ObjectId, *, limit: int = 20, skip: int = 0
    ) -> RepositoryPage[AudioEventDocument]:
        return await self.list_page(
            filters={"user_id": user_id},
            limit=limit,
            skip=skip,
        )


class FeedbackRepository(MongoRepository[FeedbackDocument]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database,
            "feedback",
            FeedbackDocument,
            filter_fields=frozenset(
                {"user_id", "translation_id", "feedback_type", "rating"}
            ),
            update_fields=frozenset({"rating", "correction"}),
            sort_fields=frozenset({"created_at", "rating"}),
        )

    async def list_for_user(
        self, user_id: ObjectId, *, limit: int = 20, skip: int = 0
    ) -> RepositoryPage[FeedbackDocument]:
        return await self.list_page(
            filters={"user_id": user_id},
            limit=limit,
            skip=skip,
        )


class ModelVersionRepository(MongoRepository[ModelVersionDocument]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database,
            "model_versions",
            ModelVersionDocument,
            filter_fields=frozenset({"model_name", "deployment_status"}),
            update_fields=frozenset(
                {"architecture", "dataset_reference", "evaluation_metrics", "deployment_status"}
            ),
            sort_fields=frozenset({"created_at", "model_name", "version"}),
        )

    async def get_version(self, model_name: str, version: str) -> ModelVersionDocument | None:
        document = await self._collection.find_one(
            {"model_name": model_name, "version": version}
        )
        return self._validate_stored(document) if document is not None else None


class UserPreferencesRepository(MongoRepository[UserPreferenceDocument]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database,
            "user_preferences",
            UserPreferenceDocument,
            filter_fields=frozenset(),
            update_fields=frozenset(
                {
                    "theme",
                    "language",
                    "voice_settings",
                    "visual_alert_settings",
                    "vibration_enabled",
                    "caption_enabled",
                    "privacy_settings",
                }
            ),
            sort_fields=frozenset({"user_id"}),
        )

    async def get_for_user(self, user_id: ObjectId) -> UserPreferenceDocument | None:
        document = await self._collection.find_one({"user_id": user_id})
        return self._validate_stored(document) if document is not None else None

    async def save_for_user(
        self, preferences: UserPreferenceDocument
    ) -> UserPreferenceDocument:
        validated = UserPreferenceDocument.model_validate(preferences)
        if validated.user_id is None:
            raise ValueError("user_id is required")
        payload = validated.model_dump(exclude={"id"}, exclude_none=True)
        document = await self._collection.find_one_and_update(
            {"user_id": validated.user_id},
            {"$set": payload},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            raise RuntimeError("MongoDB did not return the saved user preferences")
        return self._validate_stored(document)

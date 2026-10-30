from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from bson import ObjectId
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from pymongo import ReturnDocument
from pydantic import ValidationError

from app.core.time import as_utc
from app.database.documents import StoredDocumentError, UserDocument


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: ObjectId
    full_name: str
    email: str
    password_hash: str
    is_active: bool
    created_at: datetime
    session_version: int
    preferred_language: str | None
    preferred_sign_language: str | None
    accessibility_preferences: dict[str, Any]


class UserRepository:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._database = database
        self._collection: AsyncCollection[dict[str, Any]] = database["users"]

    async def create(self, full_name: str, email: str, password_hash: str) -> UserRecord:
        created_at = datetime.now(timezone.utc)
        document = UserDocument(
            full_name=full_name.strip(),
            email=email.strip().lower(),
            password_hash=password_hash,
            is_active=True,
            session_version=0,
            created_at=created_at,
        )
        result = await self._collection.insert_one(
            document.model_dump(by_alias=True, exclude_none=True)
        )
        return UserRecord(
            id=result.inserted_id,
            full_name=document.full_name,
            email=email.strip().lower(),
            password_hash=password_hash,
            is_active=True,
            created_at=created_at,
            session_version=0,
            preferred_language=None,
            preferred_sign_language=None,
            accessibility_preferences={},
        )

    async def get_by_email(self, email: str) -> UserRecord | None:
        document = await self._collection.find_one({"email": email.strip().lower()})
        return self._to_record(document) if document is not None else None

    async def get_by_id(self, user_id: ObjectId) -> UserRecord | None:
        document = await self._collection.find_one({"_id": user_id})
        return self._to_record(document) if document is not None else None

    async def update_profile(
        self,
        user_id: ObjectId,
        updates: Mapping[str, Any],
    ) -> UserRecord | None:
        if not updates:
            return await self.get_by_id(user_id)
        document = await self._collection.find_one_and_update(
            {"_id": user_id, "is_active": True},
            {
                "$set": {
                    **updates,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return self._to_record(document) if document is not None else None

    async def increment_session_version(self, user_id: ObjectId) -> None:
        await self._collection.update_one(
            {"_id": user_id},
            {"$inc": {"session_version": 1}},
        )

    async def save_password_reset_token(
        self,
        user_id: ObjectId,
        token_hash: str,
        expires_at: datetime,
    ) -> bool:
        result = await self._collection.update_one(
            {"_id": user_id, "is_active": True},
            {
                "$set": {
                    "password_reset_token_hash": token_hash,
                    "password_reset_expires_at": expires_at,
                }
            },
        )
        return result.matched_count == 1

    async def clear_password_reset_token(self, token_hash: str) -> None:
        await self._collection.update_one(
            {"password_reset_token_hash": token_hash},
            {
                "$unset": {
                    "password_reset_token_hash": "",
                    "password_reset_expires_at": "",
                }
            },
        )

    async def reset_password(
        self,
        token_hash: str,
        password_hash: str,
        now: datetime,
    ) -> UserRecord | None:
        document = await self._collection.find_one_and_update(
            {
                "password_reset_token_hash": token_hash,
                "password_reset_expires_at": {"$gt": now},
                "is_active": True,
            },
            {
                "$set": {"password_hash": password_hash},
                "$unset": {
                    "password_reset_token_hash": "",
                    "password_reset_expires_at": "",
                },
                "$inc": {"session_version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        return self._to_record(document) if document is not None else None

    async def delete_account_data(self, user_id: ObjectId) -> None:
        for collection_name in (
            "translation_history",
            "notifications",
            "audio_events",
            "feedback",
            "user_preferences",
        ):
            await self._database[collection_name].delete_many(
                {"user_id": user_id}
            )
        conversations = self._database["conversations"]
        await conversations.delete_many({"participants": [user_id]})
        await conversations.update_many(
            {"participants": user_id},
            {
                "$pull": {"participants": user_id},
                "$unset": {f"preferred_languages.{user_id}": ""},
            },
        )
        await self._collection.delete_one({"_id": user_id})

    @staticmethod
    def _to_record(document: dict[str, Any]) -> UserRecord:
        try:
            stored = UserDocument.model_validate(document)
        except ValidationError as error:
            raise StoredDocumentError("users") from error
        if stored.id is None:
            raise StoredDocumentError("users")
        return UserRecord(
            id=stored.id,
            full_name=stored.full_name,
            email=stored.email,
            password_hash=stored.password_hash,
            is_active=stored.is_active,
            created_at=as_utc(stored.created_at),
            session_version=stored.session_version,
            preferred_language=stored.preferred_language,
            preferred_sign_language=stored.preferred_sign_language,
            accessibility_preferences=stored.accessibility_preferences,
        )

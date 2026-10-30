from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.database.documents import (
    AudioEventDocument,
    ConversationDocument,
    FeedbackDocument,
    ModelVersionDocument,
    NotificationDocument,
    StoredDocumentError,
    SupportedSignDocument,
    UserPreferenceDocument,
)
from app.database.repositories.documents import (
    AudioEventRepository,
    ConversationRepository,
    FeedbackRepository,
    ModelVersionRepository,
    NotificationRepository,
    SupportedSignsRepository,
    UserPreferencesRepository,
)
from app.database.repositories.history import HistoryRepository
from conftest import FakeDatabase


def test_supported_sign_repository_validates_crud_search_and_pagination() -> None:
    async def scenario() -> None:
        database = FakeDatabase()
        repository = SupportedSignsRepository(database)  # type: ignore[arg-type]
        created_at = datetime.now(timezone.utc)
        first = await repository.create(
            SupportedSignDocument(
                sign_id="hello",
                sign_name="Hello",
                sign_category="greeting",
                language="isl",
                created_at=created_at,
            )
        )
        await repository.create(
            SupportedSignDocument(
                sign_id="thanks",
                sign_name="Thank you",
                sign_category="greeting",
                language="isl",
                created_at=created_at + timedelta(seconds=1),
            )
        )

        page = await repository.list_page(
            filters={"language": "isl"},
            search="thank",
            limit=1,
        )
        assert [item.sign_id for item in page.items] == ["thanks"]
        assert page.limit == 1
        assert page.skip == 0

        updated = await repository.update_by_id(
            first.id,
            {"description": "A verified label description"},
        )
        assert updated is not None
        assert updated.description == "A verified label description"
        assert await repository.get_by_id(first.id) == updated
        with pytest.raises(ValueError, match="Update is invalid"):
            await repository.update_by_id(
                first.id,
                {"verification_status": "unrecognized"},
            )
        assert await repository.delete_by_id(first.id)
        assert await repository.get_by_id(first.id) is None

        with pytest.raises(ValueError, match="limit"):
            await repository.list_page(limit=101)
        with pytest.raises(ValueError, match="Unsupported filter"):
            await repository.list_page(filters={"user_id": ObjectId()})

    import anyio

    anyio.run(scenario)


def test_notification_retrieval_is_user_scoped_paginated_and_markable() -> None:
    async def scenario() -> None:
        database = FakeDatabase()
        repository = NotificationRepository(database)  # type: ignore[arg-type]
        first_user = ObjectId()
        second_user = ObjectId()
        now = datetime.now(timezone.utc)
        notifications = [
            NotificationDocument(
                user_id=first_user,
                notification_type="caption",
                title=f"Message {index}",
                message="Someone is speaking",
                read_status=index == 1,
                created_at=now + timedelta(seconds=index),
            )
            for index in range(3)
        ]
        first = await repository.create(notifications[0])
        await repository.create(notifications[1])
        await repository.create(
            NotificationDocument(
                user_id=second_user,
                notification_type="caption",
                title="Private message",
                message="Private",
                created_at=now,
            )
        )

        page = await repository.list_for_user(first_user, read_status=False, limit=1)
        assert len(page.items) == 1
        assert page.items[0].user_id == first_user
        assert page.items[0].read_status is False
        assert await repository.mark_read(first.id, first_user)
        assert not await repository.mark_read(first.id, second_user)
        assert await repository.delete_for_user(first.id, first_user)
        assert not await repository.delete_for_user(first.id, first_user)

    import anyio

    anyio.run(scenario)


def test_history_supports_pagination_aggregation_and_manual_retention() -> None:
    async def scenario() -> None:
        database = FakeDatabase()
        repository = HistoryRepository(
            database,  # type: ignore[arg-type]
            retention_days=30,
        )
        user_id = ObjectId()
        for text in ("one", "two", "three"):
            await repository.create(
                user_id,
                direction="sign_to_speech",
                source_language="isl",
                target_language="en",
                input_text=text,
                output_text=text,
                confidence=None,
            )

        page = await repository.list_for_user(
            user_id,
            search=None,
            language=None,
            created_after=None,
            created_before=None,
            limit=2,
            skip=1,
        )
        assert len(page) == 2
        assert len(await repository.aggregate_counts_by_direction(user_id)) == 1

        old_record = {
            "user_id": user_id,
            "direction": "speech_to_sign",
            "source_language": "en",
            "target_language": "isl",
            "input_text": "old",
            "output_text": "old",
            "created_at": datetime.now(timezone.utc) - timedelta(days=31),
        }
        database["translation_history"].documents.append(
            {"_id": ObjectId(), **old_record}
        )
        assert await repository.purge_expired(dry_run=True) == 1
        assert await repository.purge_expired(dry_run=False) == 1
        assert await repository.purge_expired(dry_run=True) == 0

    import anyio

    anyio.run(scenario)


def test_invalid_documents_are_rejected_on_write_and_reported_on_read() -> None:
    with pytest.raises(ValidationError):
        NotificationDocument(
            user_id=ObjectId(),
            notification_type="caption",
            title="Invalid",
            message="Invalid priority",
            priority="emergency",  # type: ignore[arg-type]
            created_at=datetime.now(timezone.utc),
        )

    async def scenario() -> None:
        database = FakeDatabase()
        repository = SupportedSignsRepository(database)  # type: ignore[arg-type]
        database["supported_signs"].documents.append(
            {
                "_id": ObjectId(),
                "sign_id": "broken",
                "sign_name": "",
                "sign_category": "greeting",
                "language": "isl",
                "created_at": datetime.now(timezone.utc),
            }
        )
        with pytest.raises(StoredDocumentError):
            await repository.get_by_id(
                database["supported_signs"].documents[0]["_id"]
            )

    import anyio

    anyio.run(scenario)


def test_history_retention_requires_explicit_configuration() -> None:
    async def scenario() -> None:
        repository = HistoryRepository(FakeDatabase())  # type: ignore[arg-type]
        with pytest.raises(RuntimeError, match="not configured"):
            await repository.purge_expired()

    import anyio

    anyio.run(scenario)


def test_remaining_domain_repositories_validate_and_scope_queries() -> None:
    async def scenario() -> None:
        database = FakeDatabase()
        user_id = ObjectId()
        now = datetime.now(timezone.utc)

        conversations = ConversationRepository(database)  # type: ignore[arg-type]
        conversation = await conversations.create(
            ConversationDocument(
                conversation_id="session-1",
                participants=[user_id],
                started_at=now,
            )
        )
        assert await conversations.get_by_conversation_id("session-1") == conversation
        assert (await conversations.list_for_participant(user_id)).items == [conversation]
        ended = await conversations.update_by_id(
            conversation.id,
            {"conversation_status": "ended", "ended_at": now},
        )
        assert ended is not None
        assert ended.conversation_status == "ended"
        assert await conversations.delete_by_id(conversation.id)

        audio_events = AudioEventRepository(database)  # type: ignore[arg-type]
        event = await audio_events.create(
            AudioEventDocument(
                user_id=user_id,
                event_type="sound",
                detected_label="doorbell",
                confidence=0.8,
                severity="important",
                created_at=now,
            )
        )
        assert (await audio_events.list_for_user(user_id)).items == [event]

        feedback = FeedbackRepository(database)  # type: ignore[arg-type]
        feedback_record = await feedback.create(
            FeedbackDocument(
                user_id=user_id,
                translation_id="translation-1",
                rating=3,
                feedback_type="correction",
                created_at=now,
            )
        )
        assert (await feedback.list_for_user(user_id)).items == [feedback_record]

        versions = ModelVersionRepository(database)  # type: ignore[arg-type]
        version = await versions.create(
            ModelVersionDocument(
                model_name="static-sign",
                version="1.0.0",
                architecture="torchscript",
                created_at=now,
            )
        )
        assert await versions.get_version("static-sign", "1.0.0") == version
        activated = await versions.update_by_id(
            version.id,
            {"deployment_status": "active"},
        )
        assert activated is not None
        assert activated.deployment_status == "active"

        preferences = UserPreferencesRepository(database)  # type: ignore[arg-type]
        saved = await preferences.save_for_user(
            UserPreferenceDocument(user_id=user_id)
        )
        assert await preferences.get_for_user(user_id) == saved
        updated = await preferences.update_by_id(
            saved.id,
            {"theme": "dark"},
        )
        assert updated is not None
        assert updated.theme == "dark"
        assert await preferences.save_for_user(
            UserPreferenceDocument(user_id=user_id, theme="light")
        )
        assert len(database["user_preferences"].documents) == 1

    import anyio

    anyio.run(scenario)

from pymongo import IndexModel

from app.database.connection import Database

INDEXES: dict[str, tuple[IndexModel, ...]] = {
    "users": (
        IndexModel([("email", 1)], unique=True, name="users_email_unique"),
        IndexModel(
            [("password_reset_token_hash", 1)],
            sparse=True,
            name="users_password_reset_token_sparse",
        ),
    ),
    "translation_history": (
        IndexModel(
            [("user_id", 1), ("created_at", -1)],
            name="history_user_created_at",
        ),
    ),
    "supported_signs": (
        IndexModel(
            [("sign_id", 1), ("language", 1)],
            unique=True,
            name="supported_signs_id_language_unique",
        ),
        IndexModel(
            [("language", 1), ("verification_status", 1), ("vocabulary_version", 1)],
            name="supported_signs_verified_version",
        ),
        IndexModel(
            [("language", 1), ("sign_category", 1), ("sign_name", 1)],
            name="supported_signs_language_category_name",
        ),
    ),
    "conversations": (
        IndexModel(
            [("conversation_id", 1)],
            unique=True,
            name="conversations_id_unique",
        ),
        IndexModel(
            [("participants", 1), ("started_at", -1)],
            name="conversations_participants_started_at",
        ),
    ),
    "notifications": (
        IndexModel(
            [("user_id", 1), ("read_status", 1), ("created_at", -1)],
            name="notifications_user_read_created_at",
        ),
    ),
    "audio_events": (
        IndexModel(
            [("user_id", 1), ("created_at", -1)],
            name="audio_events_user_created_at",
        ),
    ),
    "feedback": (
        IndexModel(
            [("user_id", 1), ("created_at", -1)],
            name="feedback_user_created_at",
        ),
        IndexModel(
            [("translation_id", 1), ("created_at", -1)],
            name="feedback_translation_created_at",
        ),
    ),
    "model_versions": (
        IndexModel(
            [("model_name", 1), ("version", 1)],
            unique=True,
            name="model_versions_name_version_unique",
        ),
        IndexModel(
            [("model_name", 1), ("deployment_status", 1)],
            name="model_versions_name_status",
        ),
    ),
    "user_preferences": (
        IndexModel(
            [("user_id", 1)],
            unique=True,
            name="preferences_user_unique",
        ),
    ),
}


async def create_indexes(database: Database) -> dict[str, list[str]]:
    created: dict[str, list[str]] = {}
    for collection_name, indexes in INDEXES.items():
        collection = database[collection_name]
        created[collection_name] = await collection.create_indexes(list(indexes))
    return created

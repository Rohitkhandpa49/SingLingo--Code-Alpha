import anyio

from bson import ObjectId

from app.database.indexes import INDEXES, create_indexes
from app.database.validation import COLLECTION_NAMES, ensure_collections
from conftest import FakeDatabase


def test_collection_setup_is_idempotent_and_preserves_existing_documents() -> None:
    async def scenario() -> None:
        database = FakeDatabase()
        users = database["users"]
        original_user = {
            "_id": ObjectId(),
            "full_name": "Asha Patel",
            "email": "asha@example.com",
            "password_hash": "$argon2id$existing-hash",
            "is_active": True,
            "created_at": "legacy-value-kept-unchanged",
        }
        users.documents.append(original_user)
        existing_validator = {"$jsonSchema": {"bsonType": "object"}}
        database.options["users"] = {
            "validator": existing_validator,
            "validationLevel": "strict",
            "validationAction": "warn",
        }

        await ensure_collections(database)  # type: ignore[arg-type]
        first_setup_options = {
            name: dict(options)
            for name, options in database.options.items()
        }
        await ensure_collections(database)  # type: ignore[arg-type]

        assert set(database.collections) == set(COLLECTION_NAMES)
        assert database.options == first_setup_options
        assert users.documents == [original_user]
        assert database.options["users"]["validationLevel"] == "strict"
        assert database.options["users"]["validationAction"] == "warn"
        assert database.options["users"]["validator"]["$and"][0] == existing_validator
        assert database.options["notifications"]["validationLevel"] == "strict"
        assert database.options["notifications"]["validationAction"] == "error"

    anyio.run(scenario)


def test_indexes_cover_required_query_patterns_and_are_repeatable() -> None:
    async def scenario() -> None:
        database = FakeDatabase()
        await ensure_collections(database)  # type: ignore[arg-type]

        first = await create_indexes(database)  # type: ignore[arg-type]
        second = await create_indexes(database)  # type: ignore[arg-type]

        assert first == second
        assert set(first) == set(COLLECTION_NAMES)
        expected_names = {
            "users_email_unique",
            "users_password_reset_token_sparse",
            "history_user_created_at",
            "supported_signs_id_language_unique",
            "conversations_id_unique",
            "notifications_user_read_created_at",
            "model_versions_name_version_unique",
            "preferences_user_unique",
        }
        actual_names = {
            str(options["name"])
            for collection in database.collections.values()
            for _, options in collection.indexes
        }
        assert expected_names <= actual_names
        assert set(first) == set(INDEXES)
        index_documents = {
            str(index["name"]): index
            for indexes in INDEXES.values()
            for index in (spec.document for spec in indexes)
        }
        assert index_documents["users_email_unique"]["unique"] is True
        assert index_documents["users_password_reset_token_sparse"]["sparse"] is True
        assert index_documents["conversations_id_unique"]["unique"] is True
        assert index_documents["supported_signs_id_language_unique"]["unique"] is True
        assert index_documents["model_versions_name_version_unique"]["unique"] is True

    anyio.run(scenario)

from typing import Any

from app.database.connection import Database

COLLECTION_NAMES = (
    "users",
    "translation_history",
    "supported_signs",
    "conversations",
    "notifications",
    "audio_events",
    "feedback",
    "model_versions",
    "user_preferences",
)

_OBJECT_ID = {"bsonType": "objectId"}
_DATE = {"bsonType": "date"}
_STRING = {"bsonType": "string"}
_BOOL = {"bsonType": "bool"}
_NUMBER = {"bsonType": ["int", "long", "double", "decimal"]}
_STRING_ARRAY = {"bsonType": "array", "items": _STRING}
_OBJECT = {"bsonType": "object"}
_OPTIONAL_STRING = {"bsonType": ["string", "null"]}
_OPTIONAL_DATE = {"bsonType": ["date", "null"]}
_OPTIONAL_NUMBER = {"bsonType": ["int", "long", "double", "decimal", "null"]}


def _and_terms(query: dict[str, Any]) -> list[dict[str, Any]]:
    terms = query.get("$and")
    if isinstance(terms, list) and set(query) == {"$and"}:
        flattened: list[dict[str, Any]] = []
        for term in terms:
            flattened.extend(_and_terms(term))
        return flattened
    return [query]


COLLECTION_VALIDATORS: dict[str, dict[str, Any]] = {
    "users": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["full_name", "email", "password_hash", "is_active", "created_at"],
            "properties": {
                "full_name": _STRING,
                "email": _STRING,
                "password_hash": _STRING,
                "is_active": _BOOL,
                "account_status": {"enum": ["active", "suspended", "deleted", None]},
                "session_version": {"bsonType": ["int", "long"], "minimum": 0},
                "created_at": _DATE,
                "updated_at": _OPTIONAL_DATE,
                "profile_image": _OPTIONAL_STRING,
                "preferred_language": {"enum": ["en", "hi", None]},
                "preferred_sign_language": _OPTIONAL_STRING,
                "accessibility_preferences": _OBJECT,
                "password_reset_token_hash": _OPTIONAL_STRING,
                "password_reset_expires_at": _OPTIONAL_DATE,
            },
        }
    },
    "translation_history": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "user_id",
                "direction",
                "source_language",
                "target_language",
                "input_text",
                "output_text",
                "created_at",
            ],
            "properties": {
                "user_id": _OBJECT_ID,
                "direction": {"enum": ["sign_to_speech", "speech_to_sign"]},
                "source_language": {"enum": ["isl", "hi", "en"]},
                "target_language": {"enum": ["isl", "hi", "en"]},
                "input_text": _STRING,
                "output_text": _STRING,
                "confidence": _OPTIONAL_NUMBER,
                "created_at": _DATE,
                "conversation_id": _OPTIONAL_STRING,
            },
        }
    },
    "supported_signs": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["sign_id", "sign_name", "sign_category", "language", "created_at"],
            "properties": {
                "sign_id": _STRING,
                "sign_name": _STRING,
                "sign_category": _STRING,
                "description": _STRING,
                "language": _STRING,
                "hand_configuration": _OPTIONAL_STRING,
                "movement_description": _OPTIONAL_STRING,
                "hand_orientation": _OPTIONAL_STRING,
                "dominant_hand": _OPTIONAL_STRING,
                "facial_expression": _OPTIONAL_STRING,
                "body_posture": _OPTIONAL_STRING,
                "animation_asset": _OPTIONAL_STRING,
                "synonyms": _STRING_ARRAY,
                "dataset_reference": _OPTIONAL_STRING,
                "verification_status": {"enum": ["unverified", "verified", "rejected"]},
                "vocabulary_version": _OPTIONAL_STRING,
                "translation_texts": _OBJECT,
                "compatible_model_versions": _STRING_ARRAY,
                "sequence_sign_ids": _STRING_ARRAY,
                "created_at": _DATE,
                "updated_at": _OPTIONAL_DATE,
            },
        }
    },
    "conversations": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "conversation_id",
                "participants",
                "conversation_status",
                "started_at",
            ],
            "properties": {
                "conversation_id": _STRING,
                "participants": {
                    "bsonType": "array",
                    "minItems": 1,
                    "maxItems": 2,
                    "items": _OBJECT_ID,
                },
                "conversation_status": {"enum": ["active", "ended"]},
                "preferred_languages": _OBJECT,
                "started_at": _DATE,
                "ended_at": _OPTIONAL_DATE,
            },
        }
    },
    "notifications": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "user_id",
                "notification_type",
                "title",
                "message",
                "priority",
                "read_status",
                "created_at",
            ],
            "properties": {
                "user_id": _OBJECT_ID,
                "notification_type": _STRING,
                "title": _STRING,
                "message": _STRING,
                "priority": {"enum": ["info", "important", "warning", "critical"]},
                "read_status": _BOOL,
                "created_at": _DATE,
            },
        }
    },
    "audio_events": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "user_id",
                "event_type",
                "detected_label",
                "confidence",
                "severity",
                "created_at",
            ],
            "properties": {
                "user_id": _OBJECT_ID,
                "event_type": _STRING,
                "detected_label": _STRING,
                "confidence": _NUMBER,
                "severity": {"enum": ["info", "important", "warning", "critical"]},
                "created_at": _DATE,
            },
        }
    },
    "feedback": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "user_id",
                "translation_id",
                "rating",
                "feedback_type",
                "created_at",
            ],
            "properties": {
                "user_id": _OBJECT_ID,
                "translation_id": _STRING,
                "rating": {"bsonType": ["int", "long"], "minimum": 1, "maximum": 5},
                "correction": _OPTIONAL_STRING,
                "feedback_type": _STRING,
                "session_id": _OPTIONAL_STRING,
                "sign_id": _OPTIONAL_STRING,
                "verification_status": {
                    "enum": ["pending_review", "reviewed", "rejected"]
                },
                "created_at": _DATE,
            },
        }
    },
    "model_versions": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "model_name",
                "version",
                "architecture",
                "evaluation_metrics",
                "deployment_status",
                "created_at",
            ],
            "properties": {
                "model_name": _STRING,
                "version": _STRING,
                "architecture": _STRING,
                "dataset_reference": _OPTIONAL_STRING,
                "evaluation_metrics": _OBJECT,
                "deployment_status": {"enum": ["staged", "active", "retired"]},
                "created_at": _DATE,
            },
        }
    },
    "user_preferences": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "user_id",
                "theme",
                "language",
                "voice_settings",
                "visual_alert_settings",
                "vibration_enabled",
                "caption_enabled",
                "privacy_settings",
            ],
            "properties": {
                "user_id": _OBJECT_ID,
                "theme": {"enum": ["light", "dark", "system"]},
                "language": {"enum": ["en", "hi"]},
                "voice_settings": _OBJECT,
                "visual_alert_settings": _OBJECT,
                "vibration_enabled": _BOOL,
                "caption_enabled": _BOOL,
                "privacy_settings": _OBJECT,
            },
        }
    },
}


async def ensure_collections(database: Database) -> None:
    existing_names = set(await database.list_collection_names())
    collection_info: dict[str, dict[str, Any]] = {}
    cursor = database.list_collections(filter={"name": {"$in": COLLECTION_NAMES}})
    async for info in cursor:
        collection_info[info["name"]] = info

    for name in COLLECTION_NAMES:
        validator = COLLECTION_VALIDATORS[name]
        if name not in existing_names:
            await database.create_collection(
                name,
                validator=validator,
                validationLevel="strict",
                validationAction="error",
            )
            continue

        options = collection_info.get(name, {}).get("options", {})
        current_validator = options.get("validator")
        if current_validator:
            terms = _and_terms(current_validator)
            if validator not in terms:
                terms.append(validator)
            validator = terms[0] if len(terms) == 1 else {"$and": terms}
        await database.command(
            {
                "collMod": name,
                "validator": validator,
                "validationLevel": options.get("validationLevel", "moderate"),
                "validationAction": options.get("validationAction", "error"),
            }
        )

from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings

Database = AsyncDatabase[dict[str, Any]]


def create_mongo_client(settings: Settings) -> AsyncMongoClient[dict[str, Any]]:
    return AsyncMongoClient(
        settings.mongodb_uri.get_secret_value(),
        appname="SignLingo API",
        maxPoolSize=settings.mongodb_max_pool_size,
        minPoolSize=settings.mongodb_min_pool_size,
        maxIdleTimeMS=settings.mongodb_max_idle_time_ms,
        connectTimeoutMS=settings.mongodb_connect_timeout_ms,
        serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
        waitQueueTimeoutMS=settings.mongodb_wait_queue_timeout_ms,
    )


def get_database_from_client(
    client: AsyncMongoClient[dict[str, Any]],
    settings: Settings,
) -> Database:
    return client.get_database(settings.mongodb_database)

import re
import os
from collections.abc import Iterator, Mapping
from types import SimpleNamespace
from typing import Any

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError, PyMongoError

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/signlingo_test")
os.environ.setdefault("MONGODB_DATABASE", "signlingo_test")
os.environ.setdefault("JWT_SECRET", "test-only-secret-that-is-at-least-32-bytes")
os.environ.setdefault("APP_ENV", "test")

from app.core.config import Settings
from app.main import create_app


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    def sort(self, key: Any, direction: int | None = None) -> "FakeCursor":
        sort_keys = key if isinstance(key, list) else [(key, direction or 1)]
        for field, order in reversed(sort_keys):
            self._documents.sort(
                key=lambda item: item.get(field),
                reverse=order < 0,
            )
        return self

    def skip(self, count: int) -> "FakeCursor":
        self._documents = self._documents[count:]
        return self

    def limit(self, count: int) -> "FakeCursor":
        self._documents = self._documents[:count]
        return self

    def __aiter__(self) -> "FakeCursor":
        self._index = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._index >= len(self._documents):
            raise StopAsyncIteration
        document = self._documents[self._index]
        self._index += 1
        return document

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        return self._documents[:length]


class FakeCollection:
    def __init__(self, name: str) -> None:
        self.name = name
        self.documents: list[dict[str, Any]] = []
        self.indexes: list[tuple[Any, dict[str, Any]]] = []
        self.fail_operations = False

    async def create_index(self, *args: Any, **kwargs: Any) -> str:
        name = str(kwargs.get("name", "test-index"))
        self.indexes.append((args[0], kwargs))
        return name

    async def create_indexes(self, indexes: list[Any]) -> list[str]:
        for index in indexes:
            self.indexes.append((index.document["key"], index.document))
        return [str(index.document["name"]) for index in indexes]

    async def find_one(self, query: Mapping[str, Any]) -> dict[str, Any] | None:
        if self.fail_operations:
            raise PyMongoError("simulated database operation failure")
        return next((item for item in self.documents if self._matches(item, query)), None)

    async def insert_one(self, document: dict[str, Any]) -> SimpleNamespace:
        if self.name == "users" and any(
            item.get("email") == document.get("email") for item in self.documents
        ):
            raise DuplicateKeyError("email must be unique")
        inserted_id = ObjectId()
        self.documents.append({**document, "_id": inserted_id})
        return SimpleNamespace(inserted_id=inserted_id)

    def find(self, query: Mapping[str, Any]) -> FakeCursor:
        return FakeCursor([item for item in self.documents if self._matches(item, query)])

    async def find_one_and_update(
        self,
        query: Mapping[str, Any],
        update: Mapping[str, Any],
        *,
        upsert: bool = False,
        return_document: Any = None,
    ) -> dict[str, Any] | None:
        for document in self.documents:
            if self._matches(document, query):
                self._apply_update(document, update)
                return document
        if not upsert:
            return None
        document = {**query, "_id": ObjectId()}
        self._apply_update(document, update)
        self.documents.append(document)
        return document

    async def update_one(
        self,
        query: Mapping[str, Any],
        update: Mapping[str, Any],
    ) -> SimpleNamespace:
        for document in self.documents:
            if self._matches(document, query):
                changes = update.get("$set", {})
                changed = any(document.get(key) != value for key, value in changes.items())
                self._apply_update(document, update)
                return SimpleNamespace(modified_count=int(changed), matched_count=1)
        return SimpleNamespace(modified_count=0, matched_count=0)

    async def update_many(
        self,
        query: Mapping[str, Any],
        update: Mapping[str, Any],
    ) -> SimpleNamespace:
        matched = 0
        for document in self.documents:
            if self._matches(document, query):
                matched += 1
                self._apply_update(document, update)
        return SimpleNamespace(matched_count=matched)

    @staticmethod
    def _apply_update(
        document: dict[str, Any],
        update: Mapping[str, Any],
    ) -> None:
        for key, value in update.get("$set", {}).items():
            path = key.split(".")
            current = document
            for segment in path[:-1]:
                nested = current.setdefault(segment, {})
                if not isinstance(nested, dict):
                    raise ValueError(f"Cannot set nested field {key!r}")
                current = nested
            current[path[-1]] = value
        for key, amount in update.get("$inc", {}).items():
            document[key] = document.get(key, 0) + amount
        for key in update.get("$unset", {}):
            path = key.split(".")
            current = document
            for segment in path[:-1]:
                nested = current.get(segment)
                if not isinstance(nested, dict):
                    break
                current = nested
            else:
                current.pop(path[-1], None)
        for key, value in update.get("$pull", {}).items():
            current = document.get(key, [])
            if isinstance(current, list):
                document[key] = [item for item in current if item != value]

    async def delete_one(self, query: Mapping[str, Any]) -> SimpleNamespace:
        for index, document in enumerate(self.documents):
            if self._matches(document, query):
                del self.documents[index]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    async def delete_many(self, query: Mapping[str, Any]) -> SimpleNamespace:
        if self.fail_operations:
            raise PyMongoError("simulated database operation failure")
        before = len(self.documents)
        self.documents = [
            item for item in self.documents if not self._matches(item, query)
        ]
        return SimpleNamespace(deleted_count=before - len(self.documents))

    async def count_documents(self, query: Mapping[str, Any]) -> int:
        return sum(self._matches(item, query) for item in self.documents)

    def aggregate(self, pipeline: list[Mapping[str, Any]]) -> FakeCursor:
        documents = list(self.documents)
        for stage in pipeline:
            if "$match" in stage:
                documents = [
                    item
                    for item in documents
                    if self._matches(item, stage["$match"])
                ]
            elif "$group" in stage:
                group = stage["$group"]
                field = group["_id"].removeprefix("$")
                grouped: dict[Any, int] = {}
                for document in documents:
                    key = document.get(field)
                    grouped[key] = grouped.get(key, 0) + 1
                documents = [
                    {"_id": key, "count": count}
                    for key, count in grouped.items()
                ]
            elif "$sort" in stage:
                documents = FakeCursor(documents).sort(
                    list(stage["$sort"].items())
                )._documents
        return FakeCursor(documents)

    @classmethod
    def _matches(cls, document: Mapping[str, Any], query: Mapping[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$and":
                if not all(cls._matches(document, condition) for condition in expected):
                    return False
                continue
            if key == "$or":
                if not any(cls._matches(document, condition) for condition in expected):
                    return False
                continue
            actual = document.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            elif isinstance(expected, dict) and "$regex" in expected:
                options = re.IGNORECASE if expected.get("$options") == "i" else 0
                candidates = actual if isinstance(actual, list) else [actual]
                if not any(
                    value is not None
                    and re.search(expected["$regex"], str(value), options) is not None
                    for value in candidates
                ):
                    return False
            elif isinstance(expected, dict):
                if "$gt" in expected and (actual is None or actual <= expected["$gt"]):
                    return False
                if "$gte" in expected and actual < expected["$gte"]:
                    return False
                if "$lte" in expected and actual > expected["$lte"]:
                    return False
                if "$lt" in expected and actual >= expected["$lt"]:
                    return False
            elif actual != expected:
                if not isinstance(actual, list) or expected == [] or expected not in actual:
                    return False
        return True


class FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}
        self.options: dict[str, dict[str, Any]] = {}
        self.fail_commands = False

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self.collections:
            self.collections[name] = FakeCollection(name)
        return self.collections[name]

    async def list_collection_names(self) -> list[str]:
        return list(self.collections)

    def list_collections(self, filter: Mapping[str, Any] | None = None) -> FakeCursor:
        infos = [
            {"name": name, "options": self.options.get(name, {})}
            for name in self.collections
        ]
        if filter and "name" in filter and "$in" in filter["name"]:
            allowed = set(filter["name"]["$in"])
            infos = [info for info in infos if info["name"] in allowed]
        return FakeCursor(infos)

    async def create_collection(
        self,
        name: str,
        **options: Any,
    ) -> FakeCollection:
        self.collections.setdefault(name, FakeCollection(name))
        self.options[name] = options
        return self.collections[name]

    async def command(self, command: str) -> dict[str, int]:
        if self.fail_commands:
            raise PyMongoError("simulated database failure")
        if command == "ping":
            return {"ok": 1}
        if "collMod" in command:
            name = command["collMod"]
            options = self.options.setdefault(name, {})
            options.update(
                validator=command["validator"],
                validationLevel=command["validationLevel"],
                validationAction=command["validationAction"],
            )
            return {"ok": 1}
        raise AssertionError(f"Unexpected database command: {command}")


@pytest.fixture
def api_client() -> Iterator[tuple[TestClient, FakeDatabase]]:
    settings = Settings(
        app_env="test",
        mongodb_uri="mongodb://localhost:27017/signlingo_test",
        mongodb_database="signlingo_test",
        jwt_secret="test-only-secret-that-is-at-least-32-bytes",
        frontend_origin="http://localhost:3000",
    )
    database = FakeDatabase()
    app = create_app(settings, database)  # type: ignore[arg-type]
    with TestClient(app) as client:
        yield client, database


@pytest.fixture
def client_and_database(
    api_client: tuple[TestClient, FakeDatabase],
) -> Iterator[tuple[TestClient, FakeDatabase]]:
    yield api_client

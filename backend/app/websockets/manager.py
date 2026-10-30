import logging
from collections import defaultdict
from typing import Any
from uuid import UUID

import anyio
from fastapi import WebSocket

from app.websockets.connection import WebSocketConnection

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self, max_connections_per_user: int) -> None:
        self._max_connections_per_user = max_connections_per_user
        self._connections: dict[UUID, WebSocketConnection] = {}
        self._by_user: dict[str, set[UUID]] = defaultdict(set)
        self._lock = anyio.Lock()

    async def register(self, user_id: str, websocket: WebSocket) -> WebSocketConnection | None:
        async with self._lock:
            if len(self._by_user[user_id]) >= self._max_connections_per_user:
                return None
            connection = WebSocketConnection(user_id=user_id, websocket=websocket)
            self._connections[connection.connection_id] = connection
            self._by_user[user_id].add(connection.connection_id)
            return connection

    async def unregister(self, connection: WebSocketConnection) -> None:
        async with self._lock:
            self._connections.pop(connection.connection_id, None)
            user_connections = self._by_user.get(connection.user_id)
            if user_connections is not None:
                user_connections.discard(connection.connection_id)
                if not user_connections:
                    self._by_user.pop(connection.user_id, None)

    async def connection_count(self, user_id: str) -> int:
        async with self._lock:
            return len(self._by_user.get(user_id, ()))

    async def close_all(self, code: int = 1012) -> None:
        async with self._lock:
            connections = list(self._connections.values())
            self._connections.clear()
            self._by_user.clear()

        for connection in connections:
            try:
                with anyio.move_on_after(1):
                    await connection.websocket.close(
                        code=code,
                        reason="Service is shutting down",
                    )
            except RuntimeError:
                logger.debug("WebSocket already closed during shutdown")

    @property
    def active_connection_count(self) -> int:
        return len(self._connections)

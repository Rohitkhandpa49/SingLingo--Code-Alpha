from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from fastapi import WebSocket


@dataclass(slots=True)
class WebSocketConnection:
    user_id: str
    websocket: WebSocket
    connection_id: UUID = field(default_factory=uuid4)
    connected_at: float = field(default_factory=monotonic)
    authenticated_at: float = field(default_factory=monotonic)
    last_sequence: int = 0
    last_timestamp: datetime | None = None
    recent_sequence_ids: deque[UUID] = field(default_factory=lambda: deque(maxlen=128))
    recent_sequence_id_set: set[UUID] = field(default_factory=set)

    def remember_sequence(self, sequence_id: UUID) -> None:
        if len(self.recent_sequence_ids) == self.recent_sequence_ids.maxlen:
            expired = self.recent_sequence_ids.popleft()
            self.recent_sequence_id_set.discard(expired)
        self.recent_sequence_ids.append(sequence_id)
        self.recent_sequence_id_set.add(sequence_id)

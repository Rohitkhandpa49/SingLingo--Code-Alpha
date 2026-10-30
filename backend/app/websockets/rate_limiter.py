from collections import defaultdict, deque
from time import monotonic

import anyio


class UserMessageRateLimiter:
    def __init__(
        self,
        messages_per_minute: int,
        *,
        window_seconds: float = 60,
        max_tracked_users: int = 10_000,
    ) -> None:
        self._messages_per_minute = messages_per_minute
        self._window_seconds = window_seconds
        self._max_tracked_users = max_tracked_users
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = anyio.Lock()

    async def allow(self, user_id: str, now: float | None = None) -> bool:
        current_time = monotonic() if now is None else now
        cutoff = current_time - self._window_seconds
        async with self._lock:
            events = self._events.get(user_id)
            if events is None and len(self._events) >= self._max_tracked_users:
                for existing_user, existing_events in list(self._events.items()):
                    while existing_events and existing_events[0] <= cutoff:
                        existing_events.popleft()
                    if not existing_events:
                        self._events.pop(existing_user, None)
            events = self._events.get(user_id)
            if events is None:
                if len(self._events) >= self._max_tracked_users:
                    return False
                events = self._events[user_id]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self._messages_per_minute:
                return False
            events.append(current_time)
            return True

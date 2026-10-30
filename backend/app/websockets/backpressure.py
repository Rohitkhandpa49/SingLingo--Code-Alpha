from typing import Any

import anyio
from fastapi import WebSocket


class SlowWebSocketClient(RuntimeError):
    pass


async def send_json_bounded(
    websocket: WebSocket,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> None:
    try:
        with anyio.fail_after(timeout_seconds):
            await websocket.send_json(payload)
    except TimeoutError as error:
        raise SlowWebSocketClient from error

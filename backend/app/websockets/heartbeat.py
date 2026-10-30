from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel


class HeartbeatMessage(APIModel):
    type: Literal["system.heartbeat"]
    action: Literal["ping", "pong"]
    nonce: str = Field(min_length=16, max_length=128)

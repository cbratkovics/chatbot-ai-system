"""WebSocket message models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class MessageType(str, Enum):
    """WebSocket message types."""

    CHAT = "chat"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"
    CLOSE = "close"


class WebSocketMessage(BaseModel):
    """WebSocket message model."""

    type: MessageType
    data: Any
    timestamp: float | None = None
    connection_id: str | None = None


class ConnectionInfo(BaseModel):
    """WebSocket connection information."""

    connection_id: str
    user_id: str | None = None
    tenant_id: str | None = None
    connected_at: datetime
    last_activity: datetime

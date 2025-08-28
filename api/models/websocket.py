"""WebSocket message models."""
from pydantic import BaseModel
from typing import Optional, Any
from enum import Enum
from datetime import datetime


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
    timestamp: Optional[float] = None
    connection_id: Optional[str] = None


class ConnectionInfo(BaseModel):
    """WebSocket connection information."""
    connection_id: str
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    connected_at: datetime
    last_activity: datetime
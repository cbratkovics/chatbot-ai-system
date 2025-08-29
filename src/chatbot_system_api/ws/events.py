"""WebSocket event system for structured communication."""

import time
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """WebSocket event types."""

    # Connection events
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_CLOSED = "connection_closed"
    CONNECTION_ERROR = "connection_error"

    # Authentication events
    AUTH_REQUEST = "auth_request"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILED = "auth_failed"

    # Chat events
    CHAT_MESSAGE = "chat_message"
    CHAT_RESPONSE = "chat_response"
    CHAT_STREAM_START = "chat_stream_start"
    CHAT_STREAM_CHUNK = "chat_stream_chunk"
    CHAT_STREAM_END = "chat_stream_end"
    CHAT_ERROR = "chat_error"

    # System events
    HEARTBEAT = "heartbeat"
    SYSTEM_MESSAGE = "system_message"
    RATE_LIMIT_WARNING = "rate_limit_warning"
    TYPING_INDICATOR = "typing_indicator"


class WebSocketEvent(BaseModel):
    """Base WebSocket event."""

    id: UUID = Field(default_factory=uuid4)
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: dict[str, Any] = Field(default_factory=dict)

    # Connection context
    connection_id: str | None = None
    tenant_id: UUID | None = None
    user_id: str | None = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}

    def to_json(self) -> str:
        """Serialize event to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "WebSocketEvent":
        """Deserialize event from JSON string."""
        return cls.model_validate_json(json_str)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return self.model_dump()


class ConnectionEvent(WebSocketEvent):
    """Connection lifecycle events."""

    def __init__(self, event_type: EventType, connection_id: str, **kwargs):
        super().__init__(type=event_type, connection_id=connection_id, data=kwargs)


class MessageEvent(WebSocketEvent):
    """Chat message events."""

    def __init__(
        self,
        content: str,
        role: str = "user",
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        **kwargs,
    ):
        super().__init__(
            type=EventType.CHAT_MESSAGE,
            data={
                "content": content,
                "role": role,
                "conversation_id": str(conversation_id) if conversation_id else None,
                "message_id": str(message_id) if message_id else None,
                **kwargs,
            },
        )


class ResponseEvent(WebSocketEvent):
    """Chat response events."""

    def __init__(
        self,
        content: str,
        model: str,
        latency_ms: float,
        cached: bool = False,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        **kwargs,
    ):
        super().__init__(
            type=EventType.CHAT_RESPONSE,
            data={
                "content": content,
                "model": model,
                "latency_ms": latency_ms,
                "cached": cached,
                "conversation_id": str(conversation_id) if conversation_id else None,
                "message_id": str(message_id) if message_id else None,
                **kwargs,
            },
        )


class StreamChunkEvent(WebSocketEvent):
    """Streaming response chunk events."""

    def __init__(
        self,
        delta: str,
        chunk_index: int,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        finish_reason: str | None = None,
        **kwargs,
    ):
        super().__init__(
            type=EventType.CHAT_STREAM_CHUNK,
            data={
                "delta": delta,
                "chunk_index": chunk_index,
                "conversation_id": str(conversation_id) if conversation_id else None,
                "message_id": str(message_id) if message_id else None,
                "finish_reason": finish_reason,
                **kwargs,
            },
        )


class StreamStartEvent(WebSocketEvent):
    """Stream start event."""

    def __init__(
        self,
        model: str,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        **kwargs,
    ):
        super().__init__(
            type=EventType.CHAT_STREAM_START,
            data={
                "model": model,
                "conversation_id": str(conversation_id) if conversation_id else None,
                "message_id": str(message_id) if message_id else None,
                **kwargs,
            },
        )


class StreamEndEvent(WebSocketEvent):
    """Stream end event."""

    def __init__(
        self,
        total_tokens: int,
        total_cost: float,
        latency_ms: float,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        **kwargs,
    ):
        super().__init__(
            type=EventType.CHAT_STREAM_END,
            data={
                "total_tokens": total_tokens,
                "total_cost": total_cost,
                "latency_ms": latency_ms,
                "conversation_id": str(conversation_id) if conversation_id else None,
                "message_id": str(message_id) if message_id else None,
                **kwargs,
            },
        )


class ErrorEvent(WebSocketEvent):
    """Error events."""

    def __init__(
        self, error_message: str, error_code: str | None = None, retryable: bool = True, **kwargs
    ):
        super().__init__(
            type=EventType.CHAT_ERROR,
            data={
                "error_message": error_message,
                "error_code": error_code,
                "retryable": retryable,
                **kwargs,
            },
        )


class HeartbeatEvent(WebSocketEvent):
    """Heartbeat/keepalive events."""

    def __init__(self, server_time: float | None = None, **kwargs):
        super().__init__(
            type=EventType.HEARTBEAT,
            data={"server_time": server_time or time.time(), "message": "pong", **kwargs},
        )


class AuthRequestEvent(WebSocketEvent):
    """Authentication request event."""

    def __init__(self, token: str, **kwargs):
        super().__init__(type=EventType.AUTH_REQUEST, data={"token": token, **kwargs})


class AuthSuccessEvent(WebSocketEvent):
    """Authentication success event."""

    def __init__(self, user_id: str, tenant_id: UUID, permissions: list = None, **kwargs):
        super().__init__(
            type=EventType.AUTH_SUCCESS,
            data={
                "user_id": user_id,
                "tenant_id": str(tenant_id),
                "permissions": permissions or [],
                "authenticated": True,
                **kwargs,
            },
        )


class AuthFailedEvent(WebSocketEvent):
    """Authentication failed event."""

    def __init__(self, reason: str, **kwargs):
        super().__init__(
            type=EventType.AUTH_FAILED, data={"reason": reason, "authenticated": False, **kwargs}
        )


class SystemMessageEvent(WebSocketEvent):
    """System message events."""

    def __init__(self, message: str, level: str = "info", **kwargs):
        super().__init__(
            type=EventType.SYSTEM_MESSAGE, data={"message": message, "level": level, **kwargs}
        )


class RateLimitWarningEvent(WebSocketEvent):
    """Rate limit warning events."""

    def __init__(
        self, requests_remaining: int, reset_time: datetime, window_seconds: int, **kwargs
    ):
        super().__init__(
            type=EventType.RATE_LIMIT_WARNING,
            data={
                "requests_remaining": requests_remaining,
                "reset_time": reset_time.isoformat(),
                "window_seconds": window_seconds,
                "message": f"Rate limit warning: {requests_remaining} requests remaining",
                **kwargs,
            },
        )


class TypingIndicatorEvent(WebSocketEvent):
    """Typing indicator events."""

    def __init__(self, is_typing: bool, conversation_id: UUID | None = None, **kwargs):
        super().__init__(
            type=EventType.TYPING_INDICATOR,
            data={
                "is_typing": is_typing,
                "conversation_id": str(conversation_id) if conversation_id else None,
                **kwargs,
            },
        )


# Event factory functions for easier creation
def create_connection_event(event_type: EventType, connection_id: str, **kwargs) -> ConnectionEvent:
    """Create a connection event."""
    return ConnectionEvent(event_type, connection_id, **kwargs)


def create_message_event(content: str, **kwargs) -> MessageEvent:
    """Create a message event."""
    return MessageEvent(content, **kwargs)


def create_error_event(error_message: str, **kwargs) -> ErrorEvent:
    """Create an error event."""
    return ErrorEvent(error_message, **kwargs)


def create_heartbeat_event(**kwargs) -> HeartbeatEvent:
    """Create a heartbeat event."""
    return HeartbeatEvent(**kwargs)

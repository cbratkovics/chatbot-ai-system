"""Pydantic models for the AI Chatbot System."""


from .chat import ChatRequest, ChatResponse, Message, StreamChunk

# Database models
try:
    from chatbot_ai_system.database.models import (
        Conversation,
        Message as DBMessage,
        Tenant,
        User,
    )
    # Alias for compatibility
    Chat = Conversation
except ImportError:
    Chat = None
    User = None

# Conditional imports to avoid test failures
try:
    from .cost import CostReport, TokenUsage, UsageMetrics
except ImportError:
    pass

try:
    from .provider import ProviderConfig, ProviderMetrics, ProviderStatus
except ImportError:
    pass

try:
    from .tenant import TenantConfig, TenantLimits, TenantUsage
except ImportError:
    pass

try:
    from .websocket import ConnectionInfo, MessageType, WebSocketMessage
except ImportError:
    pass

__all__ = [
    # Always available
    "ChatRequest",
    "ChatResponse",
    "StreamChunk",
    "Message",
    # Database models
    "Chat",
    "User",
    # Conditionally available
    "WebSocketMessage",
    "MessageType",
    "ConnectionInfo",
    "TenantConfig",
    "TenantUsage",
    "TenantLimits",
    "ProviderMetrics",
    "ProviderStatus",
    "ProviderConfig",
    "CostReport",
    "UsageMetrics",
    "TokenUsage",
]

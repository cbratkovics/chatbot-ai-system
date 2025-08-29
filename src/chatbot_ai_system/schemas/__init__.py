"""Data schemas and models for AI Chatbot System."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    """Chat message."""

    role: Literal["system", "user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata")


class ChatRequest(BaseModel):
    """Chat completion request."""

    model_config = ConfigDict(extra="allow")

    messages: list[dict[str, Any]] = Field(..., description="Conversation messages")
    model: str = Field(default="gpt-3.5-turbo", description="Model to use")
    provider: str = Field(default="mock", description="Provider to use")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int | None = Field(default=1000, ge=1, description="Maximum tokens")
    stream: bool = Field(default=False, description="Stream response")
    tenant_id: str | None = Field(default=None, description="Tenant identifier")


class ChatResponse(BaseModel):
    """Chat completion response."""

    id: str = Field(..., description="Response ID")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    provider: str = Field(..., description="Provider used")
    choices: list[dict[str, Any]] = Field(..., description="Response choices")
    usage: dict[str, int] | None = Field(default=None, description="Token usage")


class StreamResponse(BaseModel):
    """Streaming response chunk."""

    id: str = Field(..., description="Response ID")
    object: str = Field(default="chat.completion.chunk", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    provider: str = Field(..., description="Provider used")
    choices: list[dict[str, Any]] = Field(..., description="Response choices")


class HealthStatus(BaseModel):
    """Health check status."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(..., description="Health status")
    version: str = Field(..., description="System version")
    service: str = Field(default="ai-chatbot-system", description="Service name")
    checks: dict[str, bool] | None = Field(default=None, description="Component checks")


__all__ = [
    "Message",
    "ChatRequest",
    "ChatResponse",
    "StreamResponse",
    "HealthStatus",
]

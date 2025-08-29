"""Chat-related Pydantic models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message roles in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """A single message in a conversation."""

    id: UUID = Field(default_factory=uuid4)
    role: MessageRole
    content: str = Field(..., min_length=1, max_length=50000)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] | None = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class ChatRequest(BaseModel):
    """Request model for chat completions."""

    messages: list[Message] = Field(..., min_items=1, max_items=100)
    model: str = Field(default="gpt-3.5-turbo", description="Model to use for completion")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=1000, ge=1, le=8000)
    stream: bool = Field(default=False)

    # Advanced parameters
    top_p: float | None = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=0.0, ge=-2.0, le=2.0)
    stop: list[str] | None = Field(default=None, max_items=4)

    # System context
    conversation_id: UUID | None = None
    tenant_id: UUID = Field(..., description="Tenant identifier for multi-tenancy")
    user_id: str | None = None

    # Metadata
    metadata: dict[str, Any] | None = None


class Usage(BaseModel):
    """Token usage information."""

    prompt_tokens: int = Field(..., ge=0)
    completion_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)

    # Cost information
    prompt_cost: float = Field(default=0.0, ge=0.0, description="Cost in USD")
    completion_cost: float = Field(default=0.0, ge=0.0)
    total_cost: float = Field(default=0.0, ge=0.0)


class ChatResponse(BaseModel):
    """Response model for chat completions."""

    id: UUID = Field(default_factory=uuid4)
    message: Message
    model: str
    usage: Usage

    # Performance metrics
    latency_ms: float = Field(..., ge=0.0, description="Response latency in milliseconds")
    cached: bool = Field(default=False, description="Whether response was served from cache")
    provider: str = Field(..., description="AI provider used")

    # Request correlation
    conversation_id: UUID | None = None
    tenant_id: UUID

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] | None = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class StreamChunk(BaseModel):
    """A chunk of streamed response."""

    id: UUID
    delta: str = Field(..., description="Incremental content")
    finish_reason: str | None = None

    # Stream metadata
    chunk_index: int = Field(..., ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class ConversationHistory(BaseModel):
    """Full conversation history."""

    conversation_id: UUID
    tenant_id: UUID
    messages: list[Message]

    # Metadata
    created_at: datetime
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    total_tokens: int = Field(default=0)
    total_cost: float = Field(default=0.0)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


class HealthCheck(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(..., description="API version")

    # Component health
    components: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Health status of individual components"
    )

    # Performance metrics
    uptime_seconds: float = Field(..., ge=0.0)
    request_count: int = Field(default=0, ge=0)
    avg_response_time_ms: float = Field(default=0.0, ge=0.0)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

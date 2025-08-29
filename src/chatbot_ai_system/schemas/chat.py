"""Chat-related schemas."""

import time
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Chat message schema."""

    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")
    name: str | None = Field(None, description="Optional name for the message author")
    tool_calls: list[dict[str, Any]] | None = Field(None, description="Tool/function calls")
    tool_call_id: str | None = Field(None, description="Tool call ID for responses")


class ChatRequest(BaseModel):
    """Chat completion request schema."""

    messages: list[dict[str, Any]] = Field(..., description="Conversation messages")
    model: str | None = Field(None, description="Model to use")
    temperature: float | None = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: int | None = Field(None, ge=1, description="Maximum tokens to generate")
    top_p: float | None = Field(1.0, ge=0, le=1, description="Nucleus sampling")
    frequency_penalty: float | None = Field(0, ge=-2, le=2, description="Frequency penalty")
    presence_penalty: float | None = Field(0, ge=-2, le=2, description="Presence penalty")
    stop: list[str] | None = Field(None, description="Stop sequences")
    stream: bool | None = Field(False, description="Stream the response")
    provider: str | None = Field(None, description="Specific provider to use")
    tools: list[dict[str, Any]] | None = Field(None, description="Available tools")
    tool_choice: Any | None = Field(None, description="Tool selection strategy")
    response_format: dict[str, Any] | None = Field(None, description="Response format")
    seed: int | None = Field(None, description="Random seed for reproducibility")
    user: str | None = Field(None, description="User identifier")

    # Additional metadata
    request_id: str | None = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str | None = Field(None, description="Tenant identifier")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")


class ChatChoice(BaseModel):
    """Chat completion choice."""

    index: int = Field(..., description="Choice index")
    message: ChatMessage = Field(..., description="Generated message")
    finish_reason: str | None = Field(None, description="Reason for completion")
    logprobs: Any | None = Field(None, description="Log probabilities")


class ChatUsage(BaseModel):
    """Token usage information."""

    prompt_tokens: int = Field(..., description="Tokens in prompt")
    completion_tokens: int = Field(..., description="Tokens in completion")
    total_tokens: int = Field(..., description="Total tokens used")

    # Cost tracking
    prompt_cost: float | None = Field(None, description="Cost of prompt tokens")
    completion_cost: float | None = Field(None, description="Cost of completion tokens")
    total_cost: float | None = Field(None, description="Total cost")


class ChatResponse(BaseModel):
    """Chat completion response schema."""

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid4()}")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = Field(..., description="Model used")
    choices: list[dict[str, Any]] = Field(..., description="Response choices")
    usage: dict[str, Any] = Field(..., description="Token usage")

    # Extended fields
    provider: str | None = Field(None, description="Provider used")
    cached: bool | None = Field(False, description="Whether response was cached")
    latency_ms: float | None = Field(None, description="Response latency in milliseconds")

    # System fingerprint for reproducibility
    system_fingerprint: str | None = Field(None, description="System configuration fingerprint")


class StreamChunk(BaseModel):
    """Streaming response chunk."""

    id: str = Field(..., description="Stream ID")
    object: str = Field(default="chat.completion.chunk", description="Object type")
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = Field(..., description="Model used")
    choices: list[dict[str, Any]] = Field(..., description="Chunk choices")


class StreamResponse(BaseModel):
    """Streaming response wrapper."""

    chunk: StreamChunk = Field(..., description="Stream chunk")
    done: bool = Field(False, description="Whether streaming is complete")
    usage: ChatUsage | None = Field(None, description="Final usage (when done)")

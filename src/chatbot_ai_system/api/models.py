"""API request and response models."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import uuid4


class ChatMessage(BaseModel):
    """Chat message model."""
    role: str = Field(..., description="Message role (system/user/assistant)")
    content: str = Field(..., description="Message content")
    name: Optional[str] = Field(None, description="Optional name")


class ChatCompletionRequest(BaseModel):
    """Chat completion request model."""
    messages: List[ChatMessage] = Field(..., description="List of messages")
    model: str = Field(default="default", description="Model to use")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum tokens")
    stream: bool = Field(default=False, description="Stream response")
    top_p: Optional[float] = Field(None, ge=0, le=1, description="Top-p sampling")
    n: int = Field(default=1, ge=1, description="Number of completions")
    stop: Optional[List[str]] = Field(None, description="Stop sequences")
    presence_penalty: Optional[float] = Field(None, ge=-2, le=2)
    frequency_penalty: Optional[float] = Field(None, ge=-2, le=2)
    user: Optional[str] = Field(None, description="User identifier")


class Choice(BaseModel):
    """Response choice."""
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    """Token usage information."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Chat completion response model."""
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid4().hex[:8]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str
    choices: List[Choice]
    usage: Usage
    cached: bool = Field(default=False, description="Response from cache")
    cache_key: Optional[str] = None
    similarity_score: float = Field(default=0.0)


class StreamChoice(BaseModel):
    """Streaming response choice."""
    index: int
    delta: Dict[str, Any]
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """Streaming chat completion chunk."""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[StreamChoice]


class ErrorResponse(BaseModel):
    """Error response model."""
    error: Dict[str, Any]
    status_code: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    version: str
    environment: str
    services: Dict[str, bool]


class AuthRequest(BaseModel):
    """Authentication request."""
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None


class AuthResponse(BaseModel):
    """Authentication response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None


class TenantInfo(BaseModel):
    """Tenant information."""
    id: str
    name: str
    created_at: datetime
    rate_limit: int
    rate_period: int
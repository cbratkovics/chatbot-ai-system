"""SDK data models."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Provider(str, Enum):
    """Supported AI providers."""
    
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LLAMA = "llama"
    CUSTOM = "custom"


class ChatMessage(BaseModel):
    """Chat message model."""
    
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata",
    )


class ChatOptions(BaseModel):
    """Options for chat requests."""
    
    provider: Provider = Field(
        default=Provider.OPENAI,
        description="AI provider to use",
    )
    model: Optional[str] = Field(
        default=None,
        description="Specific model to use",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="Maximum tokens to generate",
    )
    stream: bool = Field(
        default=False,
        description="Enable streaming responses",
    )
    top_p: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Top-p sampling",
    )
    frequency_penalty: Optional[float] = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Frequency penalty",
    )
    presence_penalty: Optional[float] = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Presence penalty",
    )
    stop: Optional[List[str]] = Field(
        default=None,
        description="Stop sequences",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User identifier for tracking",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier",
    )
    enable_cache: bool = Field(
        default=True,
        description="Enable response caching",
    )
    retry_on_failure: bool = Field(
        default=True,
        description="Enable automatic retry on failure",
    )
    timeout: Optional[float] = Field(
        default=30.0,
        description="Request timeout in seconds",
    )


class ChatResponse(BaseModel):
    """Chat response model."""
    
    id: str = Field(..., description="Response ID")
    content: str = Field(..., description="Generated content")
    provider: str = Field(..., description="Provider that generated response")
    model: str = Field(..., description="Model used")
    usage: Optional[Dict[str, int]] = Field(
        default=None,
        description="Token usage information",
    )
    finish_reason: Optional[str] = Field(
        default=None,
        description="Reason for completion",
    )
    created_at: float = Field(..., description="Timestamp of creation")
    latency: Optional[float] = Field(
        default=None,
        description="Response latency in seconds",
    )
    cached: bool = Field(
        default=False,
        description="Whether response was served from cache",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata",
    )


class EmbeddingRequest(BaseModel):
    """Embedding request model."""
    
    text: str = Field(..., description="Text to embed")
    provider: Provider = Field(
        default=Provider.OPENAI,
        description="Provider to use for embeddings",
    )
    model: Optional[str] = Field(
        default=None,
        description="Embedding model to use",
    )
    dimensions: Optional[int] = Field(
        default=None,
        description="Embedding dimensions",
    )


class EmbeddingResponse(BaseModel):
    """Embedding response model."""
    
    embedding: List[float] = Field(..., description="Embedding vector")
    provider: str = Field(..., description="Provider used")
    model: str = Field(..., description="Model used")
    dimensions: int = Field(..., description="Embedding dimensions")
    usage: Optional[Dict[str, int]] = Field(
        default=None,
        description="Token usage",
    )


class ModelInfo(BaseModel):
    """Information about an available model."""
    
    provider: Provider = Field(..., description="Model provider")
    model_id: str = Field(..., description="Model identifier")
    display_name: str = Field(..., description="Display name")
    description: Optional[str] = Field(
        default=None,
        description="Model description",
    )
    context_window: Optional[int] = Field(
        default=None,
        description="Context window size",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="Maximum output tokens",
    )
    cost_per_token: Optional[float] = Field(
        default=None,
        description="Cost per token",
    )
    supports_streaming: bool = Field(
        default=True,
        description="Whether model supports streaming",
    )
    supports_functions: bool = Field(
        default=False,
        description="Whether model supports function calling",
    )
    supports_vision: bool = Field(
        default=False,
        description="Whether model supports vision",
    )
    is_available: bool = Field(
        default=True,
        description="Whether model is currently available",
    )


class RAGQuery(BaseModel):
    """RAG query model."""
    
    query: str = Field(..., description="User query")
    top_k: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of documents to retrieve",
    )
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score",
    )
    collection: Optional[str] = Field(
        default=None,
        description="Collection to search in",
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadata filters",
    )
    rerank: bool = Field(
        default=False,
        description="Whether to rerank results",
    )


class RAGDocument(BaseModel):
    """RAG document model."""
    
    id: str = Field(..., description="Document ID")
    content: str = Field(..., description="Document content")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata",
    )
    score: Optional[float] = Field(
        default=None,
        description="Relevance score",
    )


class RAGResponse(BaseModel):
    """RAG response model."""
    
    query: str = Field(..., description="Original query")
    documents: List[RAGDocument] = Field(..., description="Retrieved documents")
    answer: Optional[str] = Field(
        default=None,
        description="Generated answer",
    )
    sources: Optional[List[str]] = Field(
        default=None,
        description="Source references",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata",
    )
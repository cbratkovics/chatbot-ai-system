"""
Base provider abstract class and common models for AI providers.
"""

import logging
import uuid
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    """Represents a single chat message."""

    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(
        default_factory=datetime.utcnow, description="Message timestamp"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": "user",
                "content": "Hello, how can you help me today?",
                "timestamp": "2024-01-15T10:00:00Z",
            }
        }
    )


class ChatResponse(BaseModel):
    """Represents a chat completion response."""

    content: str = Field(..., description="Response content")
    model: str = Field(..., description="Model used for generation")
    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique request ID"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    cached: bool = Field(False, description="Whether the response was cached")
    usage: Optional[Dict[str, int]] = Field(None, description="Token usage statistics")
    provider: str = Field(..., description="Provider name (openai, anthropic)")
    finish_reason: Optional[str] = Field(None, description="Completion finish reason")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "I can help you with various tasks...",
                "model": "gpt-3.5-turbo",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2024-01-15T10:00:01Z",
                "cached": False,
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                "provider": "openai",
                "finish_reason": "stop",
            }
        }
    )


class ProviderError(Exception):
    """Base exception for provider-related errors."""

    def __init__(
        self, 
        message: str, 
        provider: Optional[str] = None, 
        status_code: Optional[int] = None, 
        details: Optional[Dict] = None,
        error_code: Optional[str] = None,
        retryable: bool = True
    ):
        """
        Initialize provider error.

        Args:
            message: Error message
            provider: Provider name
            status_code: HTTP status code if applicable
            details: Additional error details
            error_code: Error code for categorization
            retryable: Whether the error is retryable
        """
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code
        self.details = details or {}
        self.error_code = error_code
        self.retryable = retryable
        self.timestamp = datetime.utcnow()


class RateLimitError(ProviderError):
    """Rate limit exceeded error."""
    
    def __init__(self, message: str, provider: Optional[str] = None, retry_after: Optional[int] = None):
        super().__init__(message, provider=provider, error_code="rate_limit", retryable=True)
        self.retry_after = retry_after


class AuthenticationError(ProviderError):
    """Authentication/API key error."""

    pass


class ModelNotFoundError(ProviderError):
    """Model not found error."""

    pass


class TimeoutError(ProviderError):
    """Request timeout error."""

    pass


class ContentFilterError(ProviderError):
    """Content was filtered/blocked by the provider."""

    pass


class QuotaExceededError(ProviderError):
    """API quota exceeded error."""

    pass


class Message(BaseModel):
    """Represents a message in a conversation."""

    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")


class TokenUsage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = Field(..., description="Number of tokens in the prompt")
    completion_tokens: int = Field(..., description="Number of tokens in the completion")
    total_tokens: int = Field(..., description="Total number of tokens")
    total_cost: Optional[float] = Field(default=None, description="Total cost in USD")


class CompletionRequest(BaseModel):
    """Request for a completion."""

    messages: List[Message] = Field(..., description="List of messages")
    model: str = Field(..., description="Model identifier")
    temperature: float = Field(default=0.7, description="Temperature for sampling")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens in response")
    stream: bool = Field(default=False, description="Whether to stream the response")
    tenant_id: Optional[uuid.UUID] = Field(default=None, description="Tenant ID for multi-tenancy")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class CompletionResponse(BaseModel):
    """Response from a completion request."""

    content: str = Field(..., description="Response content")
    model: str = Field(..., description="Model used for generation")
    usage: Optional[TokenUsage] = Field(default=None, description="Token usage statistics")
    finish_reason: Optional[str] = Field(default=None, description="Reason for completion")
    cached: bool = Field(default=False, description="Whether response was cached")
    cache_key: Optional[str] = Field(default=None, description="Cache key if cached")
    similarity_score: Optional[float] = Field(default=None, description="Semantic similarity score")


class StreamChunk(BaseModel):
    """A chunk of streamed response."""

    content: str = Field(..., description="Chunk content")
    is_final: bool = Field(default=False, description="Whether this is the final chunk")
    usage: Optional[TokenUsage] = Field(default=None, description="Token usage (if final)")


class StreamResponse:
    """Represents a streaming response."""
    
    def __init__(
        self,
        chunks: AsyncIterator[StreamChunk],
        model: str,
        request_id: Optional[str] = None
    ):
        self.chunks = chunks
        self.model = model
        self.request_id = request_id or str(uuid.uuid4())


class ProviderConfig(BaseModel):
    """Provider configuration."""
    
    api_key: str = Field(..., description="API key for the provider")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum number of retry attempts")
    base_url: Optional[str] = Field(default=None, description="Base URL for the provider API")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Additional headers")


class ErrorResponse(BaseModel):
    """Error response from provider."""
    
    error_type: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    provider: Optional[str] = Field(default=None, description="Provider name")
    status_code: Optional[int] = Field(default=None, description="HTTP status code")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional details")


class ProviderStatus(str, Enum):
    """Provider status enum."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    

class ProviderMetrics(BaseModel):
    """Provider metrics."""
    success_rate: float = Field(default=1.0, description="Success rate (0-1)")
    average_latency: float = Field(default=0.0, description="Average latency in milliseconds")
    total_requests: int = Field(default=0, description="Total requests made")
    successful_requests: int = Field(default=0, description="Successful requests")
    failed_requests: int = Field(default=0, description="Failed requests")


class BaseProvider(ABC):
    """Abstract base class for AI providers."""

    def __init__(self, api_key: str, timeout: int = 30, max_retries: int = 3):
        """
        Initialize the provider.

        Args:
            api_key: API key for the provider
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.provider_name = self.__class__.__name__.replace("Provider", "").lower()
        self.name = self.provider_name  # Alias for compatibility
        self.status = ProviderStatus.HEALTHY
        self.metrics = ProviderMetrics()
        self._semaphore = asyncio.Semaphore(10)  # Default concurrency limit

    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> ChatResponse:
        """
        Generate a chat completion.

        Args:
            messages: List of chat messages
            model: Model identifier
            temperature: Temperature for sampling
            max_tokens: Maximum tokens in response
            **kwargs: Additional provider-specific parameters

        Returns:
            ChatResponse: The completion response

        Raises:
            ProviderError: If an error occurs during generation
        """
        pass
        
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Complete a request using the provider."""
        # Convert ChatMessages to Messages
        chat_messages = [ChatMessage(role=msg.role, content=msg.content) for msg in request.messages]
        
        # Call the chat method
        response = await self.chat(
            messages=chat_messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        # Convert ChatResponse to CompletionResponse
        return CompletionResponse(
            content=response.content,
            model=response.model,
            usage=TokenUsage(
                prompt_tokens=response.usage.get("prompt_tokens", 0) if response.usage else 0,
                completion_tokens=response.usage.get("completion_tokens", 0) if response.usage else 0,
                total_tokens=response.usage.get("total_tokens", 0) if response.usage else 0
            ) if response.usage else None,
            finish_reason=response.finish_reason,
            cached=response.cached
        )

    @abstractmethod
    async def stream(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream a chat completion.

        Args:
            messages: List of chat messages
            model: Model identifier
            temperature: Temperature for sampling
            max_tokens: Maximum tokens in response
            **kwargs: Additional provider-specific parameters

        Yields:
            StreamChunk: Chunks of the streamed response

        Raises:
            ProviderError: If an error occurs during streaming
        """
        pass
        
    async def complete_stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Stream completion for a request."""
        # Convert Messages to ChatMessages
        chat_messages = [ChatMessage(role=msg.role, content=msg.content) for msg in request.messages]
        
        # Stream using the provider's stream method  
        async for chunk in self.stream(
            messages=chat_messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        ):
            yield chunk

    @abstractmethod
    async def validate_model(self, model: str) -> bool:
        """
        Validate if a model is supported by this provider.

        Args:
            model: Model identifier

        Returns:
            bool: True if model is supported
        """
        pass

    @abstractmethod
    def get_supported_models(self) -> List[str]:
        """
        Get list of supported models.

        Returns:
            List[str]: List of supported model identifiers
        """
        pass
        
    def supports_model(self, model: str) -> bool:
        """Check if the provider supports a specific model."""
        return model in self.get_supported_models()
        
    def is_healthy(self) -> bool:
        """Check if the provider is healthy."""
        return self.status == ProviderStatus.HEALTHY
        
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the provider."""
        return {
            "status": self.status.value,
            "name": self.name,
            "healthy": self.is_healthy(),
            "metrics": {
                "success_rate": self.metrics.success_rate,
                "average_latency": self.metrics.average_latency,
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests
            }
        }

    def _log_request(self, model: str, messages: List[ChatMessage], **kwargs) -> None:
        """
        Log request details.

        Args:
            model: Model identifier
            messages: Chat messages
            **kwargs: Additional parameters
        """
        logger.info(
            f"Provider {self.provider_name} request",
            extra={
                "provider": self.provider_name,
                "model": model,
                "message_count": len(messages),
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens"),
            },
        )

    def _log_response(self, response: ChatResponse, duration: Optional[float] = None) -> None:
        """
        Log response details.

        Args:
            response: Chat response
            duration: Request duration in seconds
        """
        logger.info(
            f"Provider {self.provider_name} response",
            extra={
                "provider": self.provider_name,
                "model": response.model,
                "request_id": response.request_id,
                "cached": response.cached,
                "duration": duration,
                "usage": response.usage,
            },
        )

    def _log_error(self, error: Exception, model: Optional[str] = None) -> None:
        """
        Log error details.

        Args:
            error: Exception that occurred
            model: Model identifier if available
        """
        logger.error(
            f"Provider {self.provider_name} error",
            extra={
                "provider": self.provider_name,
                "model": model,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            exc_info=True,
        )

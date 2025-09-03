"""
Base provider abstract class and common models for AI providers.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field
import uuid
import logging

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    """Represents a single chat message."""
    
    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Message timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "Hello, how can you help me today?",
                "timestamp": "2024-01-15T10:00:00Z"
            }
        }


class ChatResponse(BaseModel):
    """Represents a chat completion response."""
    
    content: str = Field(..., description="Response content")
    model: str = Field(..., description="Model used for generation")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique request ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    cached: bool = Field(False, description="Whether the response was cached")
    usage: Optional[Dict[str, int]] = Field(None, description="Token usage statistics")
    provider: str = Field(..., description="Provider name (openai, anthropic)")
    finish_reason: Optional[str] = Field(None, description="Completion finish reason")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "I can help you with various tasks...",
                "model": "gpt-3.5-turbo",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2024-01-15T10:00:01Z",
                "cached": False,
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30
                },
                "provider": "openai",
                "finish_reason": "stop"
            }
        }


class ProviderError(Exception):
    """Base exception for provider-related errors."""
    
    def __init__(self, message: str, provider: str = None, status_code: int = None, details: Dict = None):
        """
        Initialize provider error.
        
        Args:
            message: Error message
            provider: Provider name
            status_code: HTTP status code if applicable
            details: Additional error details
        """
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.details = details or {}
        self.timestamp = datetime.utcnow()


class RateLimitError(ProviderError):
    """Rate limit exceeded error."""
    pass


class AuthenticationError(ProviderError):
    """Authentication/API key error."""
    pass


class ModelNotFoundError(ProviderError):
    """Model not found error."""
    pass


class TimeoutError(ProviderError):
    """Request timeout error."""
    pass


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
    
    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
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
    
    def _log_request(self, model: str, messages: List[ChatMessage], **kwargs):
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
                "max_tokens": kwargs.get("max_tokens")
            }
        )
    
    def _log_response(self, response: ChatResponse, duration: float = None):
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
                "usage": response.usage
            }
        )
    
    def _log_error(self, error: Exception, model: str = None):
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
                "error_message": str(error)
            },
            exc_info=True
        )
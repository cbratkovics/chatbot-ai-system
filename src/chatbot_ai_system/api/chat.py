"""
Chat API endpoint with provider factory pattern and Redis caching.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from ..cache.cache_key_generator import CacheKeyGenerator
from ..cache.redis_cache import RedisCache
from ..config import Settings, get_settings
from ..providers.anthropic_provider import AnthropicProvider
from ..providers.base import (AuthenticationError, BaseProvider, ChatMessage,
                              ModelNotFoundError, ProviderError,
                              RateLimitError, TimeoutError)
from ..providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

# Initialize cache components
redis_cache: Optional[RedisCache] = None
cache_key_generator: Optional[CacheKeyGenerator] = None

# Create router
router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={
        404: {"description": "Not found"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"},
    },
)


class ChatCompletionRequest(BaseModel):
    """Chat completion request model."""

    message: str = Field(..., description="The user message", min_length=1, max_length=10000)
    model: str = Field(..., description="Model identifier")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(None, gt=0, le=8192, description="Maximum tokens in response")
    system_prompt: Optional[str] = Field(None, description="System prompt for context")
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        None, description="Previous messages in the conversation"
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, v):
        """Validate and sanitize message."""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        # Basic sanitization
        v = v.strip()
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "message": "What is the capital of France?",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 150,
                "system_prompt": "You are a helpful assistant.",
                "conversation_history": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                ],
            }
        }


class ChatCompletionResponse(BaseModel):
    """Chat completion response model."""

    response: str = Field(..., description="The AI response")
    model: str = Field(..., description="Model used")
    request_id: str = Field(..., description="Unique request identifier")
    timestamp: str = Field(..., description="Response timestamp")
    cached: bool = Field(False, description="Whether response was cached")
    cache_key: Optional[str] = Field(None, description="Cache key used")
    similarity_score: Optional[float] = Field(
        None, description="Similarity score for semantic cache hit"
    )
    usage: Optional[Dict[str, int]] = Field(None, description="Token usage statistics")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "The capital of France is Paris.",
                "model": "gpt-3.5-turbo",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2024-01-15T10:00:00Z",
                "cached": False,
                "cache_key": "chat:v1:gpt-3.5-turbo:abc123...",
                "similarity_score": None,
                "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
            }
        }


class ProviderFactory:
    """Factory for creating AI provider instances."""

    # Model to provider mapping
    MODEL_PROVIDER_MAP = {
        # OpenAI models
        "gpt-3.5-turbo": "openai",
        "gpt-3.5-turbo-16k": "openai",
        "gpt-4": "openai",
        "gpt-4-turbo-preview": "openai",
        "gpt-4-32k": "openai",
        "gpt-4-1106-preview": "openai",
        "gpt-4-0125-preview": "openai",
        # Anthropic models
        "claude-3-opus-20240229": "anthropic",
        "claude-3-sonnet-20240229": "anthropic",
        "claude-3-haiku-20240307": "anthropic",
        "claude-2.1": "anthropic",
        "claude-2.0": "anthropic",
        "claude-instant-1.2": "anthropic",
    }

    @classmethod
    def create_provider(cls, model: str, settings: Settings) -> BaseProvider:
        """
        Create a provider instance based on the model.

        Args:
            model: Model identifier
            settings: Application settings

        Returns:
            BaseProvider: Provider instance

        Raises:
            ModelNotFoundError: If model is not supported
            AuthenticationError: If API key is not configured
        """
        # Determine provider from model
        provider_name = cls.MODEL_PROVIDER_MAP.get(model)

        if not provider_name:
            raise ModelNotFoundError(
                f"Model '{model}' is not supported. Supported models: {list(cls.MODEL_PROVIDER_MAP.keys())}",
                provider=None,
                status_code=404,
            )

        # Create provider instance
        if provider_name == "openai":
            if not settings.has_openai_key:
                raise AuthenticationError(
                    "OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.",
                    provider="openai",
                    status_code=401,
                )
            return OpenAIProvider(
                api_key=settings.openai_api_key,
                timeout=settings.request_timeout,
                max_retries=settings.max_retries,
            )

        elif provider_name == "anthropic":
            if not settings.has_anthropic_key:
                raise AuthenticationError(
                    "Anthropic API key not configured. Please set ANTHROPIC_API_KEY environment variable.",
                    provider="anthropic",
                    status_code=401,
                )
            return AnthropicProvider(
                api_key=settings.anthropic_api_key,
                timeout=settings.request_timeout,
                max_retries=settings.max_retries,
            )

        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    @classmethod
    def get_supported_models(cls) -> List[str]:
        """Get list of all supported models."""
        return list(cls.MODEL_PROVIDER_MAP.keys())

    @classmethod
    def get_provider_for_model(cls, model: str) -> Optional[str]:
        """Get provider name for a model."""
        return cls.MODEL_PROVIDER_MAP.get(model)


@router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completion(
    request: ChatCompletionRequest,
    settings: Settings = Depends(get_settings),
    cache_control: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
) -> ChatCompletionResponse:
    """
    Generate a chat completion using the specified model.

    Args:
        request: Chat completion request
        settings: Application settings

    Returns:
        ChatCompletionResponse: The completion response

    Raises:
        HTTPException: If an error occurs
    """
    # Generate request ID
    request_id = str(uuid.uuid4())

    logger.info(
        "Chat completion request",
        extra={
            "request_id": request_id,
            "model": request.model,
            "message_length": len(request.message),
            "temperature": request.temperature,
        },
    )

    try:
        # Create provider
        provider = ProviderFactory.create_provider(request.model, settings)

        # Prepare messages
        messages = []

        # Add system prompt if provided
        if request.system_prompt:
            messages.append(ChatMessage(role="system", content=request.system_prompt))

        # Add conversation history if provided
        if request.conversation_history:
            for msg in request.conversation_history:
                messages.append(ChatMessage(role=msg["role"], content=msg["content"]))

        # Add current message
        messages.append(ChatMessage(role="user", content=request.message))

        # Generate completion
        response = await provider.chat(
            messages=messages,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        # Update response with our request ID
        response.request_id = request_id

        # Create API response
        api_response = ChatCompletionResponse(
            response=response.content,
            model=response.model,
            request_id=response.request_id,
            timestamp=response.timestamp.isoformat(),
            cached=response.cached,
            usage=response.usage,
        )

        logger.info(
            "Chat completion successful",
            extra={
                "request_id": request_id,
                "model": response.model,
                "usage": response.usage,
                "cached": response.cached,
            },
        )

        return api_response

    except AuthenticationError as e:
        logger.error(f"Authentication error: {e}", extra={"request_id": request_id})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    except ModelNotFoundError as e:
        logger.error(f"Model not found: {e}", extra={"request_id": request_id})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    except RateLimitError as e:
        logger.error(f"Rate limit exceeded: {e}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": str(e.details.get("retry_after", 60))},
        )

    except TimeoutError as e:
        logger.error(f"Request timeout: {e}", extra={"request_id": request_id})
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e))

    except ProviderError as e:
        logger.error(f"Provider error: {e}", extra={"request_id": request_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    except Exception as e:
        logger.error(
            "Unexpected error in chat completion", extra={"request_id": request_id}, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.get("/models")
async def get_supported_models(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """
    Get list of supported models.

    Returns:
        Dict containing supported models and their providers
    """
    models = ProviderFactory.get_supported_models()

    # Group by provider
    models_by_provider = {}
    for model in models:
        provider = ProviderFactory.get_provider_for_model(model)
        if provider not in models_by_provider:
            models_by_provider[provider] = []
        models_by_provider[provider].append(model)

    # Check which providers are configured
    configured_providers = []
    if settings.has_openai_key:
        configured_providers.append("openai")
    if settings.has_anthropic_key:
        configured_providers.append("anthropic")

    return {
        "models": models,
        "models_by_provider": models_by_provider,
        "configured_providers": configured_providers,
        "total_models": len(models),
    }


@router.get("/health")
async def health_check(settings: Settings = Depends(get_settings)) -> Dict[str, str]:
    """
    Health check endpoint for the chat service.

    Returns:
        Dict with health status
    """
    return {
        "status": "healthy",
        "service": "chat",
        "timestamp": datetime.utcnow().isoformat(),
        "providers_configured": {
            "openai": settings.has_openai_key,
            "anthropic": settings.has_anthropic_key,
        },
        "cache_enabled": settings.cache_enabled,
    }


# Cache management endpoints


@router.post("/cache/warm")
async def warm_cache(
    common_queries: List[Dict[str, Any]], settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """
    Warm the cache with common queries.

    Args:
        common_queries: List of common query/response pairs
        settings: Application settings

    Returns:
        Dict with warming results
    """
    if not settings.cache_enabled or not redis_cache:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache is not enabled or not available",
        )

    try:
        count = await redis_cache.warm_cache(common_queries)
        return {
            "status": "success",
            "warmed_items": count,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error warming cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to warm cache: {str(e)}",
        )


@router.get("/cache/stats")
async def get_cache_stats(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dict with cache statistics
    """
    if not settings.cache_enabled or not redis_cache:
        return {"cache_enabled": False, "message": "Cache is not enabled or not available"}

    try:
        stats = await redis_cache.get_stats()
        health = await redis_cache.health_check()

        return {
            "cache_enabled": True,
            "stats": stats.to_dict(),
            "health": health,
            "configuration": {
                "ttl_seconds": settings.cache_ttl_seconds,
                "compression_enabled": settings.cache_compression_enabled,
                "compression_threshold": settings.cache_compression_threshold,
                "semantic_cache_enabled": settings.semantic_cache_enabled,
                "semantic_threshold": settings.semantic_cache_threshold,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {"cache_enabled": True, "error": str(e), "timestamp": datetime.utcnow().isoformat()}


@router.delete("/cache")
async def clear_cache(
    pattern: Optional[str] = None,
    model: Optional[str] = None,
    user_id: Optional[str] = None,
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """
    Clear cached items.

    Args:
        pattern: Optional pattern to match keys
        model: Optional model to clear cache for
        user_id: Optional user ID to clear cache for
        settings: Application settings

    Returns:
        Dict with clear results
    """
    if not settings.cache_enabled or not redis_cache:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache is not enabled or not available",
        )

    try:
        # Generate pattern if model or user_id specified
        if model or user_id:
            if cache_key_generator:
                pattern = cache_key_generator.generate_pattern(model, user_id)

        # Clear cache
        if pattern:
            count = await redis_cache.invalidate_cache(pattern=pattern)
        else:
            # Clear all
            success = await redis_cache.clear_all()
            count = -1 if success else 0

        return {
            "status": "success",
            "cleared_items": count,
            "pattern": pattern,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}",
        )


# Initialize cache on module load
async def initialize_cache(settings: Settings):
    """Initialize Redis cache and key generator."""
    global redis_cache, cache_key_generator

    if settings.cache_enabled:
        try:
            # Create Redis cache instance
            redis_cache = RedisCache(
                redis_url=settings.redis_url,
                max_connections=settings.redis_max_connections,
                ttl_seconds=settings.cache_ttl_seconds,
                compression_threshold=settings.cache_compression_threshold,
                enable_compression=settings.cache_compression_enabled,
                enable_circuit_breaker=settings.cache_circuit_breaker_enabled,
            )

            # Connect to Redis
            await redis_cache.connect()

            # Create cache key generator
            cache_key_generator = CacheKeyGenerator(
                semantic_cache_enabled=settings.semantic_cache_enabled,
                similarity_threshold=settings.semantic_cache_threshold,
            )

            logger.info("Cache system initialized successfully")

            # Warm cache if enabled
            if settings.cache_warming_enabled:
                # Define common queries for warming
                common_queries = [
                    {
                        "key": "chat:v1:gpt-3.5-turbo:common_hello",
                        "response": {
                            "content": "Hello! How can I assist you today?",
                            "model": "gpt-3.5-turbo",
                            "usage": {
                                "prompt_tokens": 10,
                                "completion_tokens": 10,
                                "total_tokens": 20,
                            },
                        },
                        "ttl": 7200,
                    }
                ]
                await redis_cache.warm_cache(common_queries)

        except Exception as e:
            logger.error(f"Failed to initialize cache: {e}")
            redis_cache = None
            cache_key_generator = None

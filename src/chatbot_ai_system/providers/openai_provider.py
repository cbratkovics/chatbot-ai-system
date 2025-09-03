"""
OpenAI provider implementation with retry logic, error handling, and streaming support.
"""

from typing import List, Optional, Dict, Any, AsyncIterator
import asyncio
import time
import logging
from openai import AsyncOpenAI
from openai import (
    APIError,
    APIConnectionError,
    APITimeoutError,
    RateLimitError as OpenAIRateLimitError,
    AuthenticationError as OpenAIAuthError,
    NotFoundError
)

from .base import (
    BaseProvider,
    ChatMessage,
    ChatResponse,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ModelNotFoundError,
    TimeoutError
)
from .streaming_mixin import StreamingOpenAIMixin, StreamChunk

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider, StreamingOpenAIMixin):
    """OpenAI provider implementation with streaming support."""
    
    SUPPORTED_MODELS = [
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
        "gpt-4",
        "gpt-4-turbo-preview",
        "gpt-4-32k",
        "gpt-4-1106-preview",
        "gpt-4-0125-preview",
    ]
    
    def __init__(self, api_key: str, timeout: int = 30, max_retries: int = 3):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        BaseProvider.__init__(self, api_key, timeout, max_retries)
        StreamingOpenAIMixin.__init__(self, chunk_size=10)
        self.client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout,
            max_retries=0  # We handle retries ourselves
        )
    
    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatResponse:
        """
        Generate a chat completion using OpenAI.
        
        Args:
            messages: List of chat messages
            model: Model identifier
            temperature: Temperature for sampling (0-2)
            max_tokens: Maximum tokens in response
            **kwargs: Additional OpenAI-specific parameters
        
        Returns:
            ChatResponse: The completion response
        
        Raises:
            ProviderError: If an error occurs during generation
        """
        # Validate model
        if not await self.validate_model(model):
            raise ModelNotFoundError(
                f"Model '{model}' is not supported by OpenAI provider",
                provider="openai"
            )
        
        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # Log request
        self._log_request(model, messages, temperature=temperature, max_tokens=max_tokens)
        
        # Prepare request parameters
        request_params = {
            "model": model,
            "messages": openai_messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            request_params["max_tokens"] = max_tokens
        
        # Add any additional OpenAI-specific parameters
        for key, value in kwargs.items():
            if key in ["top_p", "n", "stream", "stop", "presence_penalty", 
                      "frequency_penalty", "logit_bias", "user", "functions", 
                      "function_call", "tools", "tool_choice", "seed"]:
                request_params[key] = value
        
        # Attempt with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                
                # Make API call
                response = await self.client.chat.completions.create(**request_params)
                
                # Calculate duration
                duration = time.time() - start_time
                
                # Extract response data
                choice = response.choices[0]
                content = choice.message.content
                finish_reason = choice.finish_reason
                
                # Create usage dict
                usage = None
                if response.usage:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                
                # Create response object
                chat_response = ChatResponse(
                    content=content,
                    model=response.model,
                    provider="openai",
                    finish_reason=finish_reason,
                    usage=usage,
                    cached=False
                )
                
                # Log response
                self._log_response(chat_response, duration)
                
                return chat_response
                
            except OpenAIAuthError as e:
                logger.error(f"OpenAI authentication error: {e}")
                raise AuthenticationError(
                    "Invalid OpenAI API key",
                    provider="openai",
                    status_code=401
                )
                
            except OpenAIRateLimitError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Calculate exponential backoff
                    delay = min(
                        self._calculate_backoff(attempt),
                        10.0  # Max delay of 10 seconds
                    )
                    logger.warning(
                        f"OpenAI rate limit hit, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"OpenAI rate limit exceeded after {self.max_retries} attempts")
                    raise RateLimitError(
                        "OpenAI rate limit exceeded",
                        provider="openai",
                        status_code=429,
                        details={"retry_after": getattr(e, "retry_after", None)}
                    )
                    
            except APITimeoutError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self._calculate_backoff(attempt)
                    logger.warning(
                        f"OpenAI request timeout, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"OpenAI request timeout after {self.max_retries} attempts")
                    raise TimeoutError(
                        f"OpenAI request timeout after {self.timeout}s",
                        provider="openai"
                    )
                    
            except NotFoundError as e:
                logger.error(f"OpenAI model not found: {e}")
                raise ModelNotFoundError(
                    f"Model '{model}' not found",
                    provider="openai",
                    status_code=404
                )
                
            except APIConnectionError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self._calculate_backoff(attempt)
                    logger.warning(
                        f"OpenAI connection error, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"OpenAI connection error after {self.max_retries} attempts")
                    raise ProviderError(
                        "Failed to connect to OpenAI API",
                        provider="openai"
                    )
                    
            except APIError as e:
                last_error = e
                # For general API errors, retry if it might be transient
                if attempt < self.max_retries - 1 and e.status_code >= 500:
                    delay = self._calculate_backoff(attempt)
                    logger.warning(
                        f"OpenAI API error {e.status_code}, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"OpenAI API error: {e}")
                    raise ProviderError(
                        f"OpenAI API error: {str(e)}",
                        provider="openai",
                        status_code=getattr(e, "status_code", None)
                    )
                    
            except Exception as e:
                logger.error(f"Unexpected error in OpenAI provider: {e}")
                self._log_error(e, model)
                raise ProviderError(
                    f"Unexpected error: {str(e)}",
                    provider="openai"
                )
        
        # If we get here, all retries failed
        if last_error:
            raise ProviderError(
                f"All retry attempts failed: {str(last_error)}",
                provider="openai"
            )
    
    async def validate_model(self, model: str) -> bool:
        """
        Validate if a model is supported by OpenAI.
        
        Args:
            model: Model identifier
        
        Returns:
            bool: True if model is supported
        """
        return model in self.SUPPORTED_MODELS
    
    def get_supported_models(self) -> List[str]:
        """
        Get list of supported OpenAI models.
        
        Returns:
            List[str]: List of supported model identifiers
        """
        return self.SUPPORTED_MODELS.copy()
    
    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay.
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            float: Delay in seconds
        """
        base_delay = 1.0
        max_delay = 10.0
        delay = min(base_delay * (2 ** attempt), max_delay)
        # Add jitter to prevent thundering herd
        import random
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter
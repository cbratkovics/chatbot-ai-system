"""
OpenAI provider implementation with retry logic, error handling, and streaming support.
"""

import asyncio
import logging
import time
from typing import AsyncIterator, List, Optional, Any, cast

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI
from openai import AuthenticationError as OpenAIAuthError
from openai import NotFoundError
from openai import RateLimitError as OpenAIRateLimitError
from openai.types.chat import ChatCompletionMessageParam

from .base import (
    AuthenticationError,
    BaseProvider,
    ChatMessage,
    ChatResponse,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
    StreamChunk,
    TimeoutError,
)
from .streaming_mixin import StreamingOpenAIMixin

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

    def __init__(self, api_key: str, timeout: int = 30, max_retries: int = 3) -> None:
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
            api_key=api_key, timeout=timeout, max_retries=0  # We handle retries ourselves
        )

    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
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
                f"Model '{model}' is not supported by OpenAI provider", provider="openai"
            )

        # Convert messages to OpenAI format with proper typing
        openai_messages: List[ChatCompletionMessageParam] = []
        for msg in messages:
            message_dict: ChatCompletionMessageParam = {
                "role": cast(Any, msg.role),  # Cast to satisfy type checker
                "content": msg.content
            }
            openai_messages.append(message_dict)

        # Log request
        self._log_request(model, messages, temperature=temperature, max_tokens=max_tokens)

        # Attempt with retries
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                # Make API call with explicit parameters
                # Build kwargs to avoid passing None values
                create_kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": openai_messages,
                    "temperature": temperature,
                    "stream": kwargs.get("stream", False),
                }
                
                if max_tokens:
                    create_kwargs["max_tokens"] = max_tokens
                if "top_p" in kwargs:
                    create_kwargs["top_p"] = kwargs["top_p"]
                if "n" in kwargs:
                    create_kwargs["n"] = kwargs["n"]
                if "stop" in kwargs:
                    create_kwargs["stop"] = kwargs["stop"]
                if "presence_penalty" in kwargs:
                    create_kwargs["presence_penalty"] = kwargs["presence_penalty"]
                if "frequency_penalty" in kwargs:
                    create_kwargs["frequency_penalty"] = kwargs["frequency_penalty"]
                if "logit_bias" in kwargs:
                    create_kwargs["logit_bias"] = kwargs["logit_bias"]
                if "user" in kwargs:
                    create_kwargs["user"] = kwargs["user"]
                if "seed" in kwargs:
                    create_kwargs["seed"] = kwargs["seed"]
                    
                response = await self.client.chat.completions.create(**create_kwargs)

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
                        "total_tokens": response.usage.total_tokens,
                    }

                # Create response object
                chat_response = ChatResponse(
                    content=content or "",  # Ensure content is never None
                    model=response.model,
                    provider="openai",
                    finish_reason=finish_reason,
                    usage=usage,
                    cached=False,
                )

                # Log response
                self._log_response(chat_response, duration)

                return chat_response

            except OpenAIAuthError as e:
                logger.error(f"OpenAI authentication error: {e}")
                raise AuthenticationError(
                    "Invalid OpenAI API key", provider="openai", status_code=401
                )

            except OpenAIRateLimitError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Calculate exponential backoff
                    delay = min(self._calculate_backoff(attempt), 10.0)  # Max delay of 10 seconds
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
                        retry_after=getattr(e, "retry_after", None),
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
                        f"OpenAI request timeout after {self.timeout}s", provider="openai"
                    )

            except NotFoundError as e:
                logger.error(f"OpenAI model not found: {e}")
                raise ModelNotFoundError(
                    f"Model '{model}' not found", provider="openai", status_code=404
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
                    raise ProviderError("Failed to connect to OpenAI API", provider="openai")

            except APIError as e:
                last_error = e
                # For general API errors, retry if it might be transient
                status_code = getattr(e, "status_code", 500)
                if attempt < self.max_retries - 1 and status_code >= 500:
                    delay = self._calculate_backoff(attempt)
                    logger.warning(
                        f"OpenAI API error {status_code}, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"OpenAI API error: {e}")
                    raise ProviderError(
                        f"OpenAI API error: {str(e)}",
                        provider="openai",
                        status_code=status_code if status_code != 500 else None,
                    )

            except Exception as e:
                logger.error(f"Unexpected error in OpenAI provider: {e}")
                self._log_error(e, model)
                raise ProviderError(f"Unexpected error: {str(e)}", provider="openai")

        # If we get here, all retries failed
        if last_error:
            raise ProviderError(f"All retry attempts failed: {str(last_error)}", provider="openai")
        
        # This should never be reached, but satisfies type checker
        raise ProviderError("Failed to get response from OpenAI", provider="openai")

    async def stream(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream chat completion from OpenAI.

        Args:
            messages: List of chat messages
            model: Model identifier
            temperature: Temperature for sampling
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters

        Returns:
            AsyncIterator[StreamChunk]: Stream of response chunks
        """
        # Delegate to the mixin's stream_chat method and convert chunk types
        async for mixin_chunk in self.stream_chat(messages, model, temperature, max_tokens, **kwargs):
            # Convert streaming_mixin.StreamChunk to base.StreamChunk
            base_chunk = StreamChunk(
                content=mixin_chunk.content,
                is_final=mixin_chunk.is_final,
                usage=None  # Usage handled separately if needed
            )
            yield base_chunk

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
        delay = min(base_delay * (2**attempt), max_delay)
        # Add jitter to prevent thundering herd
        import random

        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter

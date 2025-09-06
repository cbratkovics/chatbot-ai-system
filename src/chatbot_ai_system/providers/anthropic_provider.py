"""
Anthropic provider implementation with retry logic, error handling, and streaming support.
"""

import asyncio
import logging
import time
from typing import AsyncIterator, List, Optional, Dict

from anthropic import APIConnectionError, APIError, APITimeoutError, AsyncAnthropic
from anthropic import AuthenticationError as AnthropicAuthError
from anthropic import NotFoundError
from anthropic import RateLimitError as AnthropicRateLimitError

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
from .streaming_mixin import StreamingAnthropicMixin

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider, StreamingAnthropicMixin):
    """Anthropic provider implementation with streaming support."""

    SUPPORTED_MODELS = [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        "claude-2.1",
        "claude-2.0",
        "claude-instant-1.2",
    ]

    def __init__(self, api_key: str, timeout: int = 30, max_retries: int = 3) -> None:
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        BaseProvider.__init__(self, api_key, timeout, max_retries)
        StreamingAnthropicMixin.__init__(self, chunk_size=10)
        self.client = AsyncAnthropic(
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
        Generate a chat completion using Anthropic.

        Args:
            messages: List of chat messages
            model: Model identifier
            temperature: Temperature for sampling (0-1)
            max_tokens: Maximum tokens in response
            **kwargs: Additional Anthropic-specific parameters

        Returns:
            ChatResponse: The completion response

        Raises:
            ProviderError: If an error occurs during generation
        """
        # Validate model
        if not await self.validate_model(model):
            raise ModelNotFoundError(
                f"Model '{model}' is not supported by Anthropic provider", provider="anthropic"
            )

        # Convert messages to Anthropic format
        # Anthropic expects system messages to be separate
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg.role == "system":
                # Concatenate system messages
                if system_message:
                    system_message += "\n\n" + msg.content
                else:
                    system_message = msg.content
            else:
                # Convert role names (user/assistant)
                role = msg.role
                if role == "user":
                    anthropic_messages.append({"role": "user", "content": msg.content})
                elif role == "assistant":
                    anthropic_messages.append({"role": "assistant", "content": msg.content})

        # Ensure conversation starts with user message
        if not anthropic_messages or anthropic_messages[0]["role"] != "user":
            # Add a minimal user message if needed
            anthropic_messages.insert(0, {"role": "user", "content": "Please continue."})

        # Ensure conversation alternates between user and assistant
        cleaned_messages: List[Dict[str, str]] = []
        last_role = None
        for msg in anthropic_messages:
            if msg["role"] == last_role:
                # Merge consecutive messages with the same role
                if cleaned_messages:
                    cleaned_messages[-1]["content"] += "\n\n" + msg["content"]
            else:
                cleaned_messages.append(msg)
                last_role = msg["role"]

        # Log request
        self._log_request(model, messages, temperature=temperature, max_tokens=max_tokens)

        # Prepare request parameters
        request_params = {
            "model": model,
            "messages": cleaned_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 2048,  # Anthropic requires max_tokens
        }

        if system_message:
            request_params["system"] = system_message

        # Add any additional Anthropic-specific parameters
        for key, value in kwargs.items():
            if key in ["top_p", "top_k", "stop_sequences", "metadata"]:
                request_params[key] = value

        # Attempt with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()

                # Make API call
                response = await self.client.messages.create(**request_params)

                # Calculate duration
                duration = time.time() - start_time

                # Extract response data
                content = response.content[0].text if response.content else ""
                stop_reason = response.stop_reason

                # Create usage dict
                usage = None
                if response.usage:
                    usage = {
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                    }

                # Create response object
                chat_response = ChatResponse(
                    content=content,
                    model=response.model,
                    provider="anthropic",
                    finish_reason=stop_reason,
                    usage=usage,
                    cached=False,
                )

                # Log response
                self._log_response(chat_response, duration)

                return chat_response

            except AnthropicAuthError as e:
                logger.error(f"Anthropic authentication error: {e}")
                raise AuthenticationError(
                    "Invalid Anthropic API key", provider="anthropic", status_code=401
                )

            except AnthropicRateLimitError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    # Calculate exponential backoff
                    delay = min(self._calculate_backoff(attempt), 10.0)  # Max delay of 10 seconds
                    logger.warning(
                        f"Anthropic rate limit hit, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Anthropic rate limit exceeded after {self.max_retries} attempts")
                    raise RateLimitError(
                        "Anthropic rate limit exceeded",
                        provider="anthropic",
                        retry_after=getattr(e, "retry_after", None),
                    )

            except APITimeoutError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Anthropic request timeout, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Anthropic request timeout after {self.max_retries} attempts")
                    raise TimeoutError(
                        f"Anthropic request timeout after {self.timeout}s", provider="anthropic"
                    )

            except NotFoundError as e:
                logger.error(f"Anthropic model not found: {e}")
                raise ModelNotFoundError(
                    f"Model '{model}' not found", provider="anthropic", status_code=404
                )

            except APIConnectionError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Anthropic connection error, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Anthropic connection error after {self.max_retries} attempts")
                    raise ProviderError("Failed to connect to Anthropic API", provider="anthropic")

            except APIError as e:
                last_error = e
                # For general API errors, retry if it might be transient
                if attempt < self.max_retries - 1 and getattr(e, "status_code", 500) >= 500:
                    delay = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Anthropic API error, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"Anthropic API error: {e}")
                    raise ProviderError(
                        f"Anthropic API error: {str(e)}",
                        provider="anthropic",
                        status_code=getattr(e, "status_code", None),
                    )

            except Exception as e:
                logger.error(f"Unexpected error in Anthropic provider: {e}")
                self._log_error(e, model)
                raise ProviderError(f"Unexpected error: {str(e)}", provider="anthropic")

        # If we get here, all retries failed
        if last_error:
            raise ProviderError(
                f"All retry attempts failed: {str(last_error)}", provider="anthropic"
            )

    async def stream(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream chat completion from Anthropic.

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
        Validate if a model is supported by Anthropic.

        Args:
            model: Model identifier

        Returns:
            bool: True if model is supported
        """
        return model in self.SUPPORTED_MODELS

    def get_supported_models(self) -> List[str]:
        """
        Get list of supported Anthropic models.

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

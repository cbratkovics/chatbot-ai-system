"""Provider A implementation with comprehensive error handling."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiohttp

from .base import (
    AuthenticationError,
    BaseProvider,
    ChatMessage,
    ChatResponse,
    ContentFilterError,
    ModelNotFoundError,
    ProviderError,
    QuotaExceededError,
    RateLimitError,
    StreamChunk,
    TokenUsage,
)

logger = logging.getLogger(__name__)


class ProviderATokenUsage(TokenUsage):
    """Provider A specific token usage with cost calculation."""
    
    model: str
    config: Any
    
    def __init__(self, prompt_tokens: int, completion_tokens: int, model: str, config: Any):
        # Initialize as Pydantic model
        super().__init__(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens
        )
        # Store additional attributes after initialization
        object.__setattr__(self, 'model', model)
        object.__setattr__(self, 'config', config)

    @property
    def prompt_cost(self) -> float:
        """Calculate prompt cost based on model and pricing."""
        cost_per_1k = self._get_model_cost(self.model, "prompt")
        return (self.prompt_tokens / 1000) * cost_per_1k

    @property
    def completion_cost(self) -> float:
        """Calculate completion cost based on model and pricing."""
        cost_per_1k = self._get_model_cost(self.model, "completion")
        return (self.completion_tokens / 1000) * cost_per_1k

    def _get_model_cost(self, model: str, token_type: str) -> float:
        """Get cost per 1k tokens for specific model and token type."""
        # Model-specific pricing
        pricing = {
            "model-4": {"prompt": 0.03, "completion": 0.06},
            "model-4-32k": {"prompt": 0.06, "completion": 0.12},
            "model-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
            "model-3.5-turbo-16k": {"prompt": 0.003, "completion": 0.004},
        }

        if model in pricing and token_type in pricing[model]:
            return pricing[model][token_type]

        # Fallback to config defaults
        return getattr(self.config, f"{token_type}_cost_per_1k", 0.002)


class ProviderA(BaseProvider):
    """Provider A implementation with HTTP API integration."""
    
    name: str = "provider_a"
    config: Any
    base_url: str
    session: Optional[aiohttp.ClientSession]
    model_mappings: Dict[str, str]

    def __init__(self, config: Any):
        # Initialize base provider with required parameters
        api_key = getattr(config, 'api_key', '')
        timeout = getattr(config, 'timeout', 30)
        max_retries = getattr(config, 'max_retries', 3)
        super().__init__(api_key=api_key, timeout=timeout, max_retries=max_retries)
        self.config = config
        self.base_url = getattr(config, 'base_url', None) or "https://api.providerA.com/v1"
        self.session = None

        # Model mappings
        self.model_mappings = {
            "model-4": "gpt-4",
            "model-4-32k": "gpt-4-32k",
            "model-3.5-turbo": "gpt-3.5-turbo",
            "model-3.5-turbo-16k": "gpt-3.5-turbo-16k",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Chatbot-System/1.0",
            }

            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers,
                connector=aiohttp.TCPConnector(limit=100, limit_per_host=10),
            )

        return self.session

    def _map_model(self, model: str) -> str:
        """Map internal model names to provider-specific names."""
        return self.model_mappings.get(model, model)

    def _convert_messages(self, messages: List[ChatMessage]) -> List[Dict[str, str]]:
        """Convert internal message format to provider format."""
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def _handle_error_response(self, status: int, response_data: Dict[str, Any]) -> None:
        """Handle error responses from Provider A API."""
        error = response_data.get("error", {})
        error_type = error.get("type", "unknown")
        error_message = error.get("message", "Unknown error")
        error_code = error.get("code")

        if status == 401:
            raise AuthenticationError(
                f"Authentication failed: {error_message}", provider=self.name
            )

        elif status == 429:
            # Extract retry-after from headers or error response
            retry_after = None
            if "retry_after" in error:
                retry_after = int(error["retry_after"])

            raise RateLimitError(
                f"Rate limit exceeded: {error_message}",
                provider=self.name
            )

        elif status == 402:
            raise QuotaExceededError(f"Quota exceeded: {error_message}", provider=self.name)

        elif status == 400 and error_code == "model_not_found":
            raise ModelNotFoundError(
                f"Model not found: {error_message}",
                provider=self.name
            )

        elif status == 400 and error_type == "policy_violation":
            raise ContentFilterError(
                f"Content policy violation: {error_message}", provider=self.name
            )

        else:
            # Generic provider error
            raise ProviderError(
                f"Provider A API error: {error_message}",
                provider=self.name,
                status_code=status
            )

    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Generate a chat completion."""
        session = await self._get_session()

        # Prepare request payload
        payload = {
            "model": self._map_model(model),
            "messages": self._convert_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            # Note: top_p, frequency_penalty, presence_penalty are provider-specific
            # and not part of base CompletionRequest
            "stream": False,
        }

        # Add provider-specific parameters from kwargs
        if "stop" in kwargs:
            payload["stop"] = kwargs["stop"]
        if "user_id" in kwargs:
            payload["user"] = kwargs["user_id"]

        logger.debug(f"Making request to Provider A: {payload['model']}")

        try:
            async with session.post(f"{self.base_url}/chat/completions", json=payload) as response:
                response_data = await response.json()

                if response.status != 200:
                    self._handle_error_response(response.status, response_data)

                # Parse successful response
                choice = response_data["choices"][0]
                usage_data = response_data.get("usage", {})

                # Create response
                return ChatResponse(
                    content=choice["message"]["content"],
                    model=model,
                    provider="provider_a",
                    cached=False,
                    usage={
                        "prompt_tokens": usage_data.get("prompt_tokens", 0),
                        "completion_tokens": usage_data.get("completion_tokens", 0),
                        "total_tokens": usage_data.get("total_tokens", 0),
                    },
                    finish_reason=choice.get("finish_reason")
                )

        except aiohttp.ClientError as e:
            raise ProviderError(
                f"HTTP client error: {str(e)}",
                provider=self.name
            ) from e

        except TimeoutError:
            raise ProviderError(
                f"Request timeout after {getattr(self.config, 'timeout', 30)}s",
                provider=self.name
            ) from None

        except json.JSONDecodeError as e:
            raise ProviderError(
                f"Invalid JSON response: {str(e)}",
                provider=self.name
            ) from e

    async def stream(  # type: ignore[override]
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion."""
        session = await self._get_session()

        # Prepare streaming request payload
        payload = {
            "model": self._map_model(model),
            "messages": self._convert_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            # Note: top_p, frequency_penalty, presence_penalty are provider-specific
            # and not part of base CompletionRequest
            "stream": True,
        }

        # Add provider-specific parameters from kwargs
        if "stop" in kwargs:
            payload["stop"] = kwargs["stop"]
        if "user_id" in kwargs:
            payload["user"] = kwargs["user_id"]

        logger.debug(f"Making streaming request to Provider A: {payload['model']}")

        try:
            async with session.post(f"{self.base_url}/chat/completions", json=payload) as response:
                if response.status != 200:
                    error_data = await response.json()
                    self._handle_error_response(response.status, error_data)

                chunk_index = 0
                request_id = uuid4()

                # Process Server-Sent Events
                async for line in response.content:
                    line = line.decode("utf-8").strip()

                    if not line or not line.startswith("data: "):
                        continue

                    # Remove 'data: ' prefix
                    data = line[6:]

                    # Check for stream end
                    if data == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(data)
                        choice = chunk_data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        content = delta.get("content", "")
                        finish_reason = choice.get("finish_reason")

                        if content or finish_reason:
                            yield StreamChunk(
                                content=content,
                                is_final=bool(finish_reason),
                                usage=None
                            )

                            chunk_index += 1

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse streaming chunk: {data}")
                        continue

        except aiohttp.ClientError as e:
            raise ProviderError(
                f"Streaming client error: {str(e)}",
                provider=self.name
            ) from e

        except TimeoutError:
            raise ProviderError(
                f"Streaming timeout after {getattr(self.config, 'timeout', 30)}s",
                provider=self.name
            ) from None
                        
    async def validate_model(self, model: str) -> bool:
        """Validate if a model is supported."""
        return model in self.get_supported_models()
        
    def get_supported_models(self) -> List[str]:
        """Get list of supported models."""
        return list(self.model_mappings.keys())

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup session."""
        if self.session and not self.session.closed:
            await self.session.close()

    def __del__(self):
        """Cleanup session on deletion."""
        if hasattr(self, "session") and self.session and not self.session.closed:
            # Schedule session cleanup
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.session.close())
            except RuntimeError:
                pass  # Event loop not available

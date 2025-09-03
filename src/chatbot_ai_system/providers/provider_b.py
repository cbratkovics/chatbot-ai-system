"""Provider B implementation with comprehensive error handling."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from uuid import uuid4

import aiohttp

from .base import (
    AuthenticationError,
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    ContentFilterError,
    Message,
    ModelNotFoundError,
    ProviderError,
    QuotaExceededError,
    RateLimitError,
    StreamChunk,
    TokenUsage,
)

logger = logging.getLogger(__name__)


class ProviderBTokenUsage(TokenUsage):
    """Provider B specific token usage with cost calculation."""

    def __init__(self, input_tokens: int, output_tokens: int, model: str, config):
        super().__init__(input_tokens, output_tokens, input_tokens + output_tokens)
        self.model = model
        self.config = config
        # Provider B uses different terminology
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    @property
    def prompt_cost(self) -> float:
        """Calculate input cost based on model and pricing."""
        cost_per_1k = self._get_model_cost(self.model, "input")
        return (self.input_tokens / 1000) * cost_per_1k

    @property
    def completion_cost(self) -> float:
        """Calculate output cost based on model and pricing."""
        cost_per_1k = self._get_model_cost(self.model, "output")
        return (self.output_tokens / 1000) * cost_per_1k

    def _get_model_cost(self, model: str, token_type: str) -> float:
        """Get cost per 1k tokens for specific model and token type."""
        # Provider B model-specific pricing
        pricing = {
            "model-3-opus": {"input": 0.015, "output": 0.075},
            "model-3-sonnet": {"input": 0.003, "output": 0.015},
            "model-3-haiku": {"input": 0.00025, "output": 0.00125},
        }

        if model in pricing and token_type in pricing[model]:
            return pricing[model][token_type]

        # Fallback to config defaults
        return getattr(self.config, f"{token_type}_cost_per_1k", 0.003)


class ProviderB(BaseProvider):
    """Provider B implementation with HTTP API integration."""

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.base_url or "https://api.provider-b.com/v1"
        self.session = None

        # Model mappings
        self.model_mappings = {
            "model-3-opus": "provider-b-3-opus-20240229",
            "model-3-sonnet": "provider-b-3-sonnet-20240229",
            "model-3-haiku": "provider-b-3-haiku-20240307",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            headers = {
                "x-api-key": self.config.api_key,
                "Content-Type": "application/json",
                "provider-b-version": "2023-06-01",
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

    def _convert_messages(self, messages: list[Message]) -> dict:
        """Convert internal message format to Provider B format."""
        system_messages = []
        conversation_messages = []

        for msg in messages:
            if msg.role == "system":
                system_messages.append(msg.content)
            else:
                conversation_messages.append({"role": msg.role, "content": msg.content})

        result = {"messages": conversation_messages}

        # Provider B uses separate system parameter
        if system_messages:
            result["system"] = "\n\n".join(system_messages)

        return result

    def _handle_error_response(self, status: int, response_data: dict) -> None:
        """Handle error responses from Provider B API."""
        error = response_data.get("error", {})
        error_type = error.get("type", "unknown")
        error_message = error.get("message", "Unknown error")

        if status == 401:
            raise AuthenticationError(
                f"Authentication failed: {error_message}", provider_name=self.name
            )

        elif status == 429:
            # Provider B includes retry info in error response
            retry_after = None
            if "retry_after" in error:
                retry_after = int(error["retry_after"])

            raise RateLimitError(
                f"Rate limit exceeded: {error_message}",
                retry_after=retry_after,
                provider_name=self.name,
            )

        elif status == 402 or error_type == "billing_error":
            raise QuotaExceededError(f"Quota exceeded: {error_message}", provider_name=self.name)

        elif status == 400 and error_type == "invalid_request_error":
            # Check if it's a model error
            if "model" in error_message.lower():
                raise ModelNotFoundError(
                    f"Model not found: {error_message}", model="unknown", provider_name=self.name
                )
            else:
                raise ProviderError(
                    f"Invalid request: {error_message}",
                    error_code="invalid_request",
                    retryable=False,
                    provider_name=self.name,
                )

        elif error_type == "policy_violation":
            raise ContentFilterError(
                f"Content policy violation: {error_message}", provider_name=self.name
            )

        else:
            # Generic provider error
            raise ProviderError(
                f"Provider B API error: {error_message}",
                error_code=error_type or f"http_{status}",
                retryable=status >= 500,  # Server errors are retryable
                provider_name=self.name,
            )

    async def _make_request(self, request: CompletionRequest) -> CompletionResponse:
        """Make completion request to Provider B."""
        session = await self._get_session()

        # Prepare request payload
        message_data = self._convert_messages(request.messages)
        payload = {
            "model": self._map_model(request.model),
            "max_tokens": request.max_tokens or 1000,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": False,
            **message_data,
        }

        if request.stop:
            payload["stop_sequences"] = request.stop

        logger.debug(f"Making request to Provider B: {payload['model']}")

        try:
            async with session.post(f"{self.base_url}/messages", json=payload) as response:
                response_data = await response.json()

                if response.status != 200:
                    self._handle_error_response(response.status, response_data)

                # Parse successful response
                usage_data = response_data.get("usage", {})

                # Create token usage with cost calculation
                usage = ProviderBTokenUsage(
                    input_tokens=usage_data.get("input_tokens", 0),
                    output_tokens=usage_data.get("output_tokens", 0),
                    model=request.model,
                    config=self.config,
                )

                # Provider B returns content as array
                content_blocks = response_data.get("content", [])
                content = ""
                if content_blocks and len(content_blocks) > 0:
                    content = content_blocks[0].get("text", "")

                return CompletionResponse(
                    id=uuid4(),
                    content=content,
                    model=request.model,
                    usage=usage,
                    provider=self.name,
                    latency_ms=0,  # Will be set by base class
                    finish_reason=response_data.get("stop_reason"),
                    metadata={
                        "provider_response_id": response_data.get("id"),
                        "provider_model": response_data.get("model"),
                        "stop_reason": response_data.get("stop_reason"),
                        "stop_sequence": response_data.get("stop_sequence"),
                    },
                )

        except aiohttp.ClientError as e:
            raise ProviderError(
                f"HTTP client error: {str(e)}",
                error_code="client_error",
                retryable=True,
                provider_name=self.name,
            ) from e

        except TimeoutError:
            raise ProviderError(
                f"Request timeout after {self.config.timeout}s",
                error_code="timeout",
                retryable=True,
                provider_name=self.name,
            ) from None

        except json.JSONDecodeError as e:
            raise ProviderError(
                f"Invalid JSON response: {str(e)}",
                error_code="invalid_response",
                retryable=True,
                provider_name=self.name,
            ) from e

    async def _make_stream_request(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Make streaming completion request to Provider B."""
        session = await self._get_session()

        # Prepare streaming request payload
        message_data = self._convert_messages(request.messages)
        payload = {
            "model": self._map_model(request.model),
            "max_tokens": request.max_tokens or 1000,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": True,
            **message_data,
        }

        if request.stop:
            payload["stop_sequences"] = request.stop

        logger.debug(f"Making streaming request to Provider B: {payload['model']}")

        try:
            async with session.post(f"{self.base_url}/messages", json=payload) as response:
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

                    try:
                        chunk_data = json.loads(data)

                        # Handle different event types
                        event_type = chunk_data.get("type")

                        if event_type == "content_block_delta":
                            delta_data = chunk_data.get("delta", {})
                            content = delta_data.get("text", "")

                            if content:
                                yield StreamChunk(
                                    id=request_id,
                                    delta=content,
                                    finish_reason=None,
                                    chunk_index=chunk_index,
                                    metadata={
                                        "provider_event_type": event_type,
                                        "delta_index": delta_data.get("index", 0),
                                    },
                                )
                                chunk_index += 1

                        elif event_type == "message_stop":
                            # End of stream
                            yield StreamChunk(
                                id=request_id,
                                delta="",
                                finish_reason="stop",
                                chunk_index=chunk_index,
                                metadata={"provider_event_type": event_type},
                            )
                            break

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse streaming chunk: {data}")
                        continue

        except aiohttp.ClientError as e:
            raise ProviderError(
                f"Streaming client error: {str(e)}",
                error_code="streaming_error",
                retryable=True,
                provider_name=self.name,
            ) from e

        except TimeoutError:
            raise ProviderError(
                f"Streaming timeout after {self.config.timeout}s",
                error_code="streaming_timeout",
                retryable=True,
                provider_name=self.name,
            ) from None

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

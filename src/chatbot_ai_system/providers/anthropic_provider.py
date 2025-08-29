"""Anthropic provider implementation."""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Anthropic model provider."""

    def __init__(
        self, client: Any | None = None, api_key: str | None = None, max_retries: int = 3
    ):
        """Initialize Anthropic provider.

        Args:
            client: Anthropic client instance
            api_key: Anthropic API key
            max_retries: Maximum retry attempts
        """
        self.client = client
        self.api_key = api_key
        self.max_retries = max_retries
        self.name = "anthropic"
        self.supported_models = [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-instant-1.2",
        ]
        self.requests_processed = 0
        self.error_count = 0

        if not self.client:
            self._init_client()

    def _init_client(self):
        """Initialize Anthropic client."""
        try:
            from anthropic import AsyncAnthropic

            self.client = AsyncAnthropic(api_key=self.api_key)
        except ImportError:
            logger.error("Anthropic library not installed")
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic client: {e}")

    async def chat_completion(self, request: dict[str, Any]) -> dict[str, Any]:
        """Create chat completion.

        Args:
            request: Chat request

        Returns:
            Chat response
        """
        try:
            model = self._map_model_name(request.get("model", "claude-3-sonnet"))
            messages = self.format_messages(
                request.get("messages", [{"role": "user", "content": request.get("message", "")}])
            )

            response = await self.client.messages.create(
                model=model,
                messages=messages,
                max_tokens=request.get("max_tokens", 150),
                temperature=request.get("temperature", 0.7),
                stream=request.get("stream", False),
            )

            self.requests_processed += 1

            if request.get("stream"):
                return response

            return self._format_response(response)

        except Exception as e:
            self.error_count += 1
            logger.error(f"Anthropic completion error: {e}")
            raise

    async def stream_completion(
        self, request: dict[str, Any]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream chat completion.

        Args:
            request: Chat request

        Yields:
            Response chunks
        """
        request["stream"] = True
        stream = await self.chat_completion(request)

        async for chunk in stream:
            yield self._format_stream_chunk(chunk)

    def format_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Format messages for Anthropic API.

        Args:
            messages: Input messages

        Returns:
            Formatted messages
        """
        formatted = []

        for message in messages:
            role = message.get("role", "user")
            if role == "system":
                role = "assistant"

            formatted.append({"role": role, "content": message.get("content", "")})

        return formatted

    def _map_model_name(self, model: str) -> str:
        """Map model name to Anthropic format.

        Args:
            model: Input model name

        Returns:
            Anthropic model name
        """
        model_map = {
            "claude-3-opus": "claude-3-opus-20240229",
            "claude-3-sonnet": "claude-3-sonnet-20240229",
            "claude-3-haiku": "claude-3-haiku-20240307",
            "claude-instant": "claude-instant-1.2",
        }

        return model_map.get(model, model)

    def _format_response(self, response: Any) -> dict[str, Any]:
        """Format Anthropic response to OpenAI format.

        Args:
            response: Anthropic response

        Returns:
            Formatted response
        """
        return {
            "id": response.id,
            "object": "chat.completion",
            "created": int(datetime.utcnow().timestamp()),
            "model": response.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response.content[0].text if response.content else "",
                    },
                    "finish_reason": response.stop_reason or "stop",
                }
            ],
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
        }

    def _format_stream_chunk(self, chunk: Any) -> dict[str, Any]:
        """Format stream chunk.

        Args:
            chunk: Stream chunk

        Returns:
            Formatted chunk
        """
        return {
            "id": getattr(chunk, "id", ""),
            "object": "chat.completion.chunk",
            "created": int(datetime.utcnow().timestamp()),
            "model": getattr(chunk, "model", ""),
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": chunk.delta.text if hasattr(chunk, "delta") else ""},
                    "finish_reason": None,
                }
            ],
        }

    def is_model_supported(self, model: str) -> bool:
        """Check if model is supported.

        Args:
            model: Model name

        Returns:
            True if supported
        """
        mapped_model = self._map_model_name(model)
        return mapped_model in self.supported_models

    async def health_check(self) -> bool:
        """Check provider health.

        Returns:
            Health status
        """
        try:
            response = await self.client.messages.create(
                model="claude-instant-1.2",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1,
            )
            return bool(response)
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for completion.

        Args:
            model: Model name
            input_tokens: Input token count
            output_tokens: Output token count

        Returns:
            Estimated cost in USD
        """
        pricing = {
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
            "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
            "claude-instant-1.2": {"input": 0.00163, "output": 0.00551},
        }

        mapped_model = self._map_model_name(model)
        model_pricing = pricing.get(mapped_model, pricing["claude-instant-1.2"])

        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]

        return input_cost + output_cost

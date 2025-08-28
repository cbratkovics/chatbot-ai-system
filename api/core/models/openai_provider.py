"""OpenAI provider implementation."""

import logging
from collections.abc import AsyncGenerator
from typing import Any

import tiktoken

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """OpenAI model provider."""

    def __init__(
        self, client: Any | None = None, api_key: str | None = None, max_retries: int = 3
    ):
        """Initialize OpenAI provider.

        Args:
            client: OpenAI client instance
            api_key: OpenAI API key
            max_retries: Maximum retry attempts
        """
        self.client = client
        self.api_key = api_key
        self.max_retries = max_retries
        self.name = "openai"
        self.supported_models = [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4-32k",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
        ]
        self.requests_processed = 0
        self.error_count = 0

        if not self.client:
            self._init_client()

    def _init_client(self):
        """Initialize OpenAI client."""
        try:
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(api_key=self.api_key)
        except ImportError:
            logger.error("OpenAI library not installed")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")

    async def chat_completion(self, request: dict[str, Any]) -> dict[str, Any]:
        """Create chat completion.

        Args:
            request: Chat request

        Returns:
            Chat response
        """
        try:
            model = request.get("model", "gpt-3.5-turbo")
            messages = request.get(
                "messages", [{"role": "user", "content": request.get("message", "")}]
            )

            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=request.get("temperature", 0.7),
                max_tokens=request.get("max_tokens", 150),
                stream=request.get("stream", False),
            )

            self.requests_processed += 1

            if request.get("stream"):
                return response

            return response.model_dump()

        except Exception as e:
            self.error_count += 1
            logger.error(f"OpenAI completion error: {e}")
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
            yield chunk.model_dump()

    async def chat_completion_with_retry(self, request: dict[str, Any]) -> dict[str, Any]:
        """Chat completion with retry logic.

        Args:
            request: Chat request

        Returns:
            Chat response
        """
        import asyncio

        for attempt in range(self.max_retries):
            try:
                return await self.chat_completion(request)
            except Exception:
                if attempt == self.max_retries - 1:
                    raise

                wait_time = 2**attempt
                logger.warning(f"Retry {attempt + 1}/{self.max_retries} after {wait_time}s")
                await asyncio.sleep(wait_time)

    def count_tokens(self, text: str, model: str = "gpt-3.5-turbo") -> int:
        """Count tokens in text.

        Args:
            text: Input text
            model: Model name

        Returns:
            Token count
        """
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.error(f"Token counting error: {e}")
            return len(text.split()) * 1.3

    def is_model_supported(self, model: str) -> bool:
        """Check if model is supported.

        Args:
            model: Model name

        Returns:
            True if supported
        """
        return model in self.supported_models

    async def health_check(self) -> bool:
        """Check provider health.

        Returns:
            Health status
        """
        try:
            response = await self.client.models.list()
            return bool(response.data)
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def format_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Format messages for OpenAI API.

        Args:
            messages: Input messages

        Returns:
            Formatted messages
        """
        formatted = []

        for message in messages:
            formatted.append(
                {"role": message.get("role", "user"), "content": message.get("content", "")}
            )

        return formatted

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
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-32k": {"input": 0.06, "output": 0.12},
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
        }

        model_pricing = pricing.get(model, pricing["gpt-3.5-turbo"])

        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]

        return input_cost + output_cost

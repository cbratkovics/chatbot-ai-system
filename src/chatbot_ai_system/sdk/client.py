"""SDK for AI Chatbot System - Client interface."""

from collections.abc import AsyncIterator
from typing import Any

import httpx

from chatbot_ai_system.config.settings import settings
from chatbot_ai_system.schemas import ChatRequest


class ChatbotClient:
    """Client for interacting with the AI Chatbot System."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        """Initialize the client."""
        self.base_url = (
            base_url or getattr(settings, "api_base_url", None) or "http://localhost:8000"
        )
        self.api_key = api_key or settings.api_key
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
        )

    async def chat(
        self, message: str, provider: str = "openai", model: str | None = None, **kwargs
    ) -> str:
        """Send a chat message and get response."""
        request = ChatRequest(
            messages=[{"role": "user", "content": message}],
            model=model or "gpt-3.5-turbo",
            provider=provider,
            **kwargs,
        )

        response = await self._client.post(
            "/api/v1/chat/completions",
            json=request.model_dump(),
        )
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def chat_stream(
        self, message: str, provider: str = "openai", model: str | None = None, **kwargs
    ) -> AsyncIterator[str]:
        """Stream chat responses."""
        request = ChatRequest(
            messages=[{"role": "user", "content": message}],
            model=model or "gpt-3.5-turbo",
            provider=provider,
            stream=True,
            **kwargs,
        )

        async with self._client.stream(
            "POST",
            "/api/v1/chat/completions",
            json=request.model_dump(),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]

    async def health_check(self) -> dict[str, Any]:
        """Check API health."""
        response = await self._client.get("/health")
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the client."""
        await self._client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args):
        """Async context manager exit."""
        await self.close()

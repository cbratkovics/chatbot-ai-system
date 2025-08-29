"""Mock provider for testing."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from chatbot_ai_system.schemas import ChatRequest


class MockProvider:
    """Mock provider for testing without real API calls."""

    async def complete(self, request: ChatRequest) -> dict[str, Any]:
        """Generate mock completion."""
        await asyncio.sleep(0.1)  # Simulate API delay

        # Get last user message
        last_message = ""
        if request.messages:
            for msg in reversed(request.messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    last_message = msg.get("content", "")
                    break

        return {
            "content": f"Mock response to: {last_message}",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25,
            },
        }

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Stream mock completion."""
        # Get last user message
        last_message = ""
        if request.messages:
            for msg in reversed(request.messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    last_message = msg.get("content", "")
                    break

        response = f"Mock streaming response to: {last_message}"

        for word in response.split():
            await asyncio.sleep(0.05)  # Simulate streaming delay
            yield word + " "

    async def health_check(self) -> bool:
        """Check mock provider health."""
        return True

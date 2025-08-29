"""Provider management and routing."""

from collections.abc import AsyncIterator
from typing import Any

from chatbot_ai_system.config import settings
from chatbot_ai_system.exceptions import ProviderException
from chatbot_ai_system.schemas import ChatRequest

# Import submodules for backward compatibility
from .anthropic_provider import AnthropicProvider
from .fallback_handler import FallbackHandler
from .model_factory import ModelFactory
from .openai_provider import OpenAIProvider


class ProviderRouter:
    """Route requests to appropriate AI providers with failover."""

    def __init__(self):
        self.providers = self._initialize_providers()
        self.fallback_order = ["openai", "anthropic", "mock"]

    def _initialize_providers(self) -> dict[str, Any]:
        """Initialize available providers."""
        providers = {}

        # Import providers here to avoid circular imports
        from chatbot_ai_system.providers.mock_provider import MockProvider

        # Always include mock for testing
        providers["mock"] = MockProvider()

        # Initialize real providers if keys are available
        if settings.openai_api_key:
            from chatbot_ai_system.providers.simple_openai import SimpleOpenAIProvider

            providers["openai"] = SimpleOpenAIProvider(settings.openai_api_key.get_secret_value())

        if settings.anthropic_api_key:
            from chatbot_ai_system.providers.anthropic_provider import AnthropicProvider

            providers["anthropic"] = AnthropicProvider(
                settings.anthropic_api_key.get_secret_value()
            )

        return providers

    async def route(self, request: ChatRequest) -> dict[str, Any]:
        """Route request to appropriate provider with failover."""
        provider_name = request.provider

        # Try primary provider
        if provider_name in self.providers:
            try:
                return await self.providers[provider_name].complete(request)
            except Exception as e:
                # Log error and try fallback
                print(f"Provider {provider_name} failed: {e}")

        # Try fallback providers
        for fallback in self.fallback_order:
            if fallback != provider_name and fallback in self.providers:
                try:
                    return await self.providers[fallback].complete(request)
                except Exception:
                    continue

        raise ProviderException("All providers failed", provider=provider_name)

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Stream response from provider."""
        provider_name = request.provider

        if provider_name in self.providers:
            async for chunk in self.providers[provider_name].stream(request):
                yield chunk
        else:
            # Fallback to mock for testing
            from chatbot_ai_system.providers.mock_provider import MockProvider

            mock = MockProvider()
            async for chunk in mock.stream(request):
                yield chunk


# Exports moved to top of file

__all__ = [
    "ProviderRouter",
    "ModelFactory",
    "OpenAIProvider",
    "AnthropicProvider",
    "FallbackHandler",
]

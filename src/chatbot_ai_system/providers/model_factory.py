"""Model factory for provider abstraction using strategy pattern."""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ModelFactory:
    """Factory for creating and managing model providers."""

    def __init__(self, load_balancing: bool = False, cost_optimization: bool = False):
        """Initialize model factory.

        Args:
            load_balancing: Enable load balancing
            cost_optimization: Enable cost optimization
        """
        self.load_balancing = load_balancing
        self.cost_optimization = cost_optimization
        self.providers = {}
        self.default_provider = "openai"
        self._current_provider_index = 0

        self._init_providers()

    def _init_providers(self):
        """Initialize model providers."""
        from .anthropic_provider import AnthropicProvider
        from .openai_provider import OpenAIProvider

        self.providers["openai"] = OpenAIProvider()
        self.providers["anthropic"] = AnthropicProvider()

    def register_provider(self, name: str, provider: Any):
        """Register new provider.

        Args:
            name: Provider name
            provider: Provider instance
        """
        self.providers[name] = provider
        logger.info(f"Registered provider: {name}")

    def get_provider(self, model: str) -> Any:
        """Get provider for model.

        Args:
            model: Model name

        Returns:
            Provider instance

        Raises:
            ValueError: If model is not supported
        """
        model_providers = {
            "gpt-4": "openai",
            "gpt-4-turbo": "openai",
            "gpt-3.5-turbo": "openai",
            "claude-3-opus": "anthropic",
            "claude-3-sonnet": "anthropic",
            "claude-instant": "anthropic",
        }

        provider_name = model_providers.get(model)
        if not provider_name:
            raise ValueError(f"Unsupported model: {model}")

        return self.providers.get(provider_name)

    def get_provider_with_load_balancing(self) -> Any:
        """Get provider with load balancing.

        Returns:
            Provider instance
        """
        provider_names = list(self.providers.keys())
        provider_name = provider_names[self._current_provider_index]
        self._current_provider_index = (self._current_provider_index + 1) % len(provider_names)

        return self.providers[provider_name]

    async def check_provider_health(self, provider_name: str) -> bool:
        """Check provider health.

        Args:
            provider_name: Provider name

        Returns:
            Health status
        """
        provider = self.providers.get(provider_name)
        if not provider:
            return False

        try:
            return await provider.health_check()
        except Exception as e:
            logger.error(f"Health check failed for {provider_name}: {e}")
            return False

    async def process_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Process chat request.

        Args:
            request: Chat request

        Returns:
            Response from provider
        """
        model = request.get("model", "gpt-3.5-turbo")

        if self.cost_optimization and request.get("optimize_cost"):
            model = self._select_cost_optimized_model(request)
            request["model"] = model

        provider = self.get_provider(model)

        try:
            response = await provider.chat_completion(request)
            response["model"] = model

            if self.cost_optimization:
                response["cost_optimized"] = True

            return response

        except Exception as e:
            logger.error(f"Request processing failed: {e}")

            from .fallback_handler import FallbackHandler

            fallback = FallbackHandler(
                primary=provider, secondary=self._get_fallback_provider(model)
            )

            response = await fallback.execute_with_fallback(request)
            response["fallback_used"] = True
            response["primary_error"] = str(e)

            return response

    def _select_cost_optimized_model(self, request: dict[str, Any]) -> str:
        """Select cost-optimized model.

        Args:
            request: Chat request

        Returns:
            Optimized model name
        """
        message = request.get("message", "")

        if len(message) < 100:
            return "gpt-3.5-turbo"

        capability = request.get("capability_required")
        if capability == "code_generation":
            return "gpt-4"
        elif capability == "mathematics":
            return "gpt-4"
        else:
            return "claude-instant"

    def _get_fallback_provider(self, model: str) -> Any:
        """Get fallback provider for model.

        Args:
            model: Model name

        Returns:
            Fallback provider
        """
        fallback_map = {
            "gpt-4": self.providers.get("anthropic"),
            "gpt-3.5-turbo": self.providers.get("anthropic"),
            "claude-3-opus": self.providers.get("openai"),
            "claude-instant": self.providers.get("openai"),
        }

        return fallback_map.get(model, self.providers.get(self.default_provider))

    def get_supported_models(self) -> list[str]:
        """Get list of supported models.

        Returns:
            List of model names
        """
        models = []
        for provider in self.providers.values():
            models.extend(provider.supported_models)
        return models

    def get_provider_stats(self) -> dict[str, Any]:
        """Get provider statistics.

        Returns:
            Provider statistics
        """
        stats = {}

        for name, provider in self.providers.items():
            stats[name] = {
                "healthy": asyncio.run(self.check_provider_health(name)),
                "supported_models": provider.supported_models,
                "requests_processed": getattr(provider, "requests_processed", 0),
                "errors": getattr(provider, "error_count", 0),
            }

        return stats

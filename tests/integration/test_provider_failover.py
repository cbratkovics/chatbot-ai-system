"""Integration tests for provider failover mechanisms."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chatbot_ai_system.providers.base import (
    ChatMessage,
    ChatResponse,
    ProviderError,
    RateLimitError,
)
from chatbot_ai_system.providers.orchestrator import (
    LoadBalancingStrategy,
    ProviderOrchestrator,
)


@pytest.mark.integration
class TestProviderFailover:
    """Test provider failover mechanisms."""

    @pytest.fixture
    async def mock_provider_a(self):
        """Create a mock provider A."""
        provider = MagicMock()
        provider.name = "provider_a"
        provider.status = "healthy"
        provider.metrics = {"success_rate": 0.95, "average_latency_ms": 100}
        provider._semaphore = asyncio.Semaphore(10)
        provider.is_healthy = MagicMock(return_value=True)
        provider.supports_model = MagicMock(return_value=True)
        provider.chat = AsyncMock(
            return_value=ChatResponse(
                content="Response from Provider A",
                model="gpt-3.5-turbo",
                provider="provider_a",
                cached=False,
            )
        )
        return provider

    @pytest.fixture
    async def mock_provider_b(self):
        """Create a mock provider B."""
        provider = MagicMock()
        provider.name = "provider_b"
        provider.status = "healthy"
        provider.metrics = {"success_rate": 0.90, "average_latency_ms": 150}
        provider._semaphore = asyncio.Semaphore(10)
        provider.is_healthy = MagicMock(return_value=True)
        provider.supports_model = MagicMock(return_value=True)
        provider.chat = AsyncMock(
            return_value=ChatResponse(
                content="Response from Provider B",
                model="gpt-3.5-turbo",
                provider="provider_b",
                cached=False,
            )
        )
        return provider

    @pytest.mark.asyncio
    async def test_automatic_failover_on_provider_error(
        self, mock_provider_a, mock_provider_b
    ):
        """Test automatic failover when primary provider fails."""
        # Configure provider A to fail
        mock_provider_a.chat.side_effect = ProviderError(
            "Service unavailable", provider="provider_a"
        )

        # Create orchestrator with both providers
        orchestrator = ProviderOrchestrator(
            providers=[mock_provider_a, mock_provider_b],
            strategy=LoadBalancingStrategy.ROUND_ROBIN,
            enable_circuit_breaker=True,
        )

        # Make a request
        messages = [ChatMessage(role="user", content="Hello")]
        response = await orchestrator.chat(
            messages=messages, model="gpt-3.5-turbo"
        )

        # Should have failed over to provider B
        assert response.content == "Response from Provider B"
        assert response.provider == "provider_b"
        assert orchestrator.failover_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_activation(
        self, mock_provider_a, mock_provider_b
    ):
        """Test circuit breaker activates after multiple failures."""
        # Configure provider A to always fail
        mock_provider_a.chat.side_effect = ProviderError(
            "Persistent error", provider="provider_a"
        )

        orchestrator = ProviderOrchestrator(
            providers=[mock_provider_a, mock_provider_b],
            strategy=LoadBalancingStrategy.ROUND_ROBIN,
            enable_circuit_breaker=True,
        )

        # Make multiple requests to trigger circuit breaker
        for _ in range(6):  # Threshold is 5
            messages = [ChatMessage(role="user", content="Test")]
            try:
                await orchestrator.chat(messages=messages, model="gpt-3.5-turbo")
            except ProviderError:
                pass

        # Circuit breaker should be open for provider A
        circuit_breaker = orchestrator.circuit_breakers["provider_a"]
        assert circuit_breaker.state == "open"

        # Future requests should go directly to provider B
        messages = [ChatMessage(role="user", content="Hello")]
        response = await orchestrator.chat(
            messages=messages, model="gpt-3.5-turbo"
        )
        assert response.provider == "provider_b"

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, mock_provider_a, mock_provider_b):
        """Test handling of rate limit errors with retry."""
        call_count = 0

        async def rate_limited_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError(
                    "Rate limit exceeded", provider="provider_a"
                )
            return ChatResponse(
                content="Success after retry",
                model="gpt-3.5-turbo",
                provider="provider_a",
                cached=False,
            )

        mock_provider_a.chat = AsyncMock(side_effect=rate_limited_then_success)

        orchestrator = ProviderOrchestrator(
            providers=[mock_provider_a, mock_provider_b],
            strategy=LoadBalancingStrategy.ROUND_ROBIN,
        )

        messages = [ChatMessage(role="user", content="Test")]
        response = await orchestrator.chat(
            messages=messages, model="gpt-3.5-turbo"
        )

        # Should retry and succeed
        assert response.content == "Success after retry"
        assert call_count == 2  # Initial attempt + retry

    @pytest.mark.asyncio
    async def test_load_balancing_strategies(
        self, mock_provider_a, mock_provider_b
    ):
        """Test different load balancing strategies."""
        # Test Round Robin
        orchestrator = ProviderOrchestrator(
            providers=[mock_provider_a, mock_provider_b],
            strategy=LoadBalancingStrategy.ROUND_ROBIN,
        )

        messages = [ChatMessage(role="user", content="Test")]

        # First request should go to provider A
        response1 = await orchestrator.chat(
            messages=messages, model="gpt-3.5-turbo"
        )
        assert response1.provider == "provider_a"

        # Second request should go to provider B
        response2 = await orchestrator.chat(
            messages=messages, model="gpt-3.5-turbo"
        )
        assert response2.provider == "provider_b"

        # Third request should go back to provider A
        response3 = await orchestrator.chat(
            messages=messages, model="gpt-3.5-turbo"
        )
        assert response3.provider == "provider_a"

    @pytest.mark.asyncio
    async def test_all_providers_down_error(
        self, mock_provider_a, mock_provider_b
    ):
        """Test error when all providers are down."""
        # Configure both providers to fail
        mock_provider_a.is_healthy.return_value = False
        mock_provider_b.is_healthy.return_value = False

        orchestrator = ProviderOrchestrator(
            providers=[mock_provider_a, mock_provider_b],
            strategy=LoadBalancingStrategy.ROUND_ROBIN,
        )

        messages = [ChatMessage(role="user", content="Test")]

        with pytest.raises(ProviderError) as exc_info:
            await orchestrator.chat(messages=messages, model="gpt-3.5-turbo")

        assert "No healthy providers available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_model_specific_routing(self, mock_provider_a, mock_provider_b):
        """Test routing based on model support."""
        # Provider A supports GPT models
        mock_provider_a.supports_model = MagicMock(
            side_effect=lambda m: m.startswith("gpt")
        )
        # Provider B supports Claude models
        mock_provider_b.supports_model = MagicMock(
            side_effect=lambda m: m.startswith("claude")
        )

        orchestrator = ProviderOrchestrator(
            providers=[mock_provider_a, mock_provider_b],
            strategy=LoadBalancingStrategy.ROUND_ROBIN,
        )

        messages = [ChatMessage(role="user", content="Test")]

        # Request for GPT model should go to provider A
        response1 = await orchestrator.chat(
            messages=messages, model="gpt-3.5-turbo"
        )
        assert response1.provider == "provider_a"

        # Request for Claude model should go to provider B
        mock_provider_b.chat.return_value = ChatResponse(
            content="Claude response",
            model="claude-3-haiku",
            provider="provider_b",
            cached=False,
        )
        response2 = await orchestrator.chat(
            messages=messages, model="claude-3-haiku"
        )
        assert response2.provider == "provider_b"

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(
        self, mock_provider_a, mock_provider_b
    ):
        """Test handling of concurrent requests."""
        orchestrator = ProviderOrchestrator(
            providers=[mock_provider_a, mock_provider_b],
            strategy=LoadBalancingStrategy.LEAST_LOADED,
        )

        messages = [ChatMessage(role="user", content="Test")]

        # Send multiple concurrent requests
        tasks = [
            orchestrator.chat(messages=messages, model="gpt-3.5-turbo")
            for _ in range(10)
        ]
        responses = await asyncio.gather(*tasks)

        # All requests should succeed
        assert len(responses) == 10
        assert all(r.content for r in responses)

        # Both providers should have been used
        providers_used = {r.provider for r in responses}
        assert "provider_a" in providers_used
        assert "provider_b" in providers_used
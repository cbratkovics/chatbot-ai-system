"""Integration tests for model switching."""

import asyncio
from unittest.mock import patch

import pytest


class TestModelSwitching:
    """Test suite for dynamic model switching."""

    @pytest.mark.asyncio
    async def test_openai_to_anthropic_switch(self, sample_chat_request):
        """Test switching from OpenAI to Anthropic model."""
        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory()

        request_openai = {**sample_chat_request, "model": "gpt-4"}
        response_openai = await factory.process_request(request_openai)
        assert response_openai["model"] == "gpt-4"

        request_anthropic = {**sample_chat_request, "model": "claude-3-opus"}
        response_anthropic = await factory.process_request(request_anthropic)
        assert response_anthropic["model"] == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_automatic_failover(self, sample_chat_request):
        """Test automatic failover when primary model fails."""
        from api.core.models.anthropic_provider import AnthropicProvider
        from api.core.models.fallback_handler import FallbackHandler
        from api.core.models.openai_provider import OpenAIProvider

        primary = OpenAIProvider()
        secondary = AnthropicProvider()

        with patch.object(primary, "chat_completion", side_effect=Exception("Primary failed")):
            with patch.object(
                secondary, "chat_completion", return_value={"response": "from secondary"}
            ):
                handler = FallbackHandler(primary=primary, secondary=secondary)
                response = await handler.execute_with_fallback(sample_chat_request)

                assert response["response"] == "from secondary"

    @pytest.mark.asyncio
    async def test_model_performance_comparison(self, sample_chat_request):
        """Test performance comparison between models."""
        import time

        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory()
        models = ["gpt-4", "claude-3-opus", "gpt-3.5-turbo"]

        performance_metrics = {}

        for model in models:
            request = {**sample_chat_request, "model": model}

            start_time = time.time()
            response = await factory.process_request(request)
            latency = (time.time() - start_time) * 1000

            performance_metrics[model] = {
                "latency_ms": latency,
                "tokens": response.get("usage", {}).get("total_tokens", 0),
            }

        assert all(metrics["latency_ms"] < 1000 for metrics in performance_metrics.values())

    @pytest.mark.asyncio
    async def test_concurrent_model_requests(self, sample_chat_request):
        """Test concurrent requests to different models."""
        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory()

        async def make_request(model):
            request = {**sample_chat_request, "model": model}
            return await factory.process_request(request)

        models = ["gpt-4", "claude-3-opus", "gpt-3.5-turbo"]
        tasks = [make_request(model) for model in models]

        responses = await asyncio.gather(*tasks)

        assert len(responses) == len(models)
        for i, response in enumerate(responses):
            assert response["model"] == models[i]

    @pytest.mark.asyncio
    async def test_model_context_preservation(self, sample_chat_request):
        """Test context preservation across model switches."""
        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory()
        session_id = "session123"

        messages = [
            {"role": "user", "content": "My name is Alice"},
            {"role": "assistant", "content": "Nice to meet you, Alice"},
            {"role": "user", "content": "What's my name?"},
        ]

        request_gpt = {
            **sample_chat_request,
            "model": "gpt-4",
            "messages": messages,
            "session_id": session_id,
        }

        response_gpt = await factory.process_request(request_gpt)
        assert "Alice" in response_gpt["choices"][0]["message"]["content"]

        request_claude = {
            **sample_chat_request,
            "model": "claude-3-opus",
            "messages": messages,
            "session_id": session_id,
        }

        response_claude = await factory.process_request(request_claude)
        assert "Alice" in response_claude["choices"][0]["message"]["content"]

    @pytest.mark.asyncio
    async def test_model_cost_optimization(self, sample_chat_request):
        """Test cost optimization through model selection."""
        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory(cost_optimization=True)

        simple_request = {**sample_chat_request, "message": "What is 2+2?", "optimize_cost": True}

        response = await factory.process_request(simple_request)

        assert response["model"] in ["gpt-3.5-turbo", "claude-instant"]
        assert response["cost_optimized"] is True

    @pytest.mark.asyncio
    async def test_model_capability_routing(self, sample_chat_request):
        """Test routing based on model capabilities."""
        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory()

        code_request = {
            **sample_chat_request,
            "message": "Write a Python function to sort a list",
            "capability_required": "code_generation",
        }

        response = await factory.process_request(code_request)
        assert response["model"] in ["gpt-4", "claude-3-opus"]

        math_request = {
            **sample_chat_request,
            "message": "Solve this calculus problem",
            "capability_required": "mathematics",
        }

        response = await factory.process_request(math_request)
        assert response["model"] in ["gpt-4", "claude-3-opus"]

    @pytest.mark.asyncio
    async def test_model_load_balancing(self):
        """Test load balancing across model providers."""
        from api.core.models.model_factory import ModelFactory

        factory = ModelFactory(load_balancing=True)

        request_counts = {"openai": 0, "anthropic": 0}

        for _ in range(100):
            provider = factory.get_provider_with_load_balancing()
            provider_name = provider.__class__.__name__.lower().replace("provider", "")
            if "openai" in provider_name:
                request_counts["openai"] += 1
            elif "anthropic" in provider_name:
                request_counts["anthropic"] += 1

        assert request_counts["openai"] > 30
        assert request_counts["anthropic"] > 30
        assert abs(request_counts["openai"] - request_counts["anthropic"]) < 20

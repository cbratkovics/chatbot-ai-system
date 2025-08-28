from unittest.mock import patch

import pytest

from api.services.llm.orchestrator import LLMOrchestrator


@pytest.mark.asyncio
async def test_llm_orchestrator_model_selection():
    with patch("app.services.llm.orchestrator.OpenAIProvider"), patch(
        "app.services.llm.orchestrator.AnthropicProvider"
    ):
        orchestrator = LLMOrchestrator()

        # Test simple query
        simple_model = orchestrator.select_model_for_query("Hi", optimize_cost=True)
        assert simple_model == "gpt-4o-mini"

        # Test complex query
        complex_query = "Explain the theory of relativity in detail " * 10
        complex_model = orchestrator.select_model_for_query(complex_query, optimize_cost=True)
        assert complex_model in ["gpt-4o", "claude-3-5-sonnet-latest"]


def test_query_complexity_classification():
    with patch("app.services.llm.orchestrator.OpenAIProvider"), patch(
        "app.services.llm.orchestrator.AnthropicProvider"
    ):
        orchestrator = LLMOrchestrator()

        # Test simple
        assert orchestrator.classify_query_complexity("Hello") == "simple"

        # Test moderate
        moderate_text = "Can you explain how this works? " * 3
        assert orchestrator.classify_query_complexity(moderate_text) == "moderate"

        # Test complex
        complex_text = "Detailed explanation " * 50
        assert orchestrator.classify_query_complexity(complex_text) == "complex"

"""Groq gpt-oss models get reasoning_effort=low so a capped answer is not all reasoning."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from chatbot_ai_system.providers.base import ChatMessage
from chatbot_ai_system.providers.groq_provider import GroqProvider


def _completion(model: str):
    return SimpleNamespace(
        model=model,
        choices=[SimpleNamespace(message=SimpleNamespace(content="hi"), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


@pytest.mark.asyncio
async def test_chat_sets_low_reasoning_effort_for_gpt_oss_only(monkeypatch):
    provider = GroqProvider(api_key="k")
    create = AsyncMock(side_effect=lambda **kw: _completion(kw["model"]))
    monkeypatch.setattr(provider, "client", MagicMock(chat=MagicMock(completions=MagicMock(create=create))))
    monkeypatch.setattr(provider, "validate_model", AsyncMock(return_value=True))

    await provider.chat([ChatMessage(role="user", content="hi")], "openai/gpt-oss-20b", max_tokens=50)
    assert create.call_args.kwargs["reasoning_effort"] == "low"
    assert create.call_args.kwargs["max_tokens"] == 50

    await provider.chat([ChatMessage(role="user", content="hi")], "some-other-model")
    assert "reasoning_effort" not in create.call_args.kwargs

    # An explicit caller value wins over the default.
    await provider.chat([ChatMessage(role="user", content="hi")], "openai/gpt-oss-120b", reasoning_effort="high")
    assert create.call_args.kwargs["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_stream_forwards_reasoning_effort(monkeypatch):
    provider = GroqProvider(api_key="k")
    seen = {}

    async def fake_stream_chat(messages, model, temperature, max_tokens, **kwargs):
        seen.update(kwargs)
        yield SimpleNamespace(content="x", is_final=False, usage=None)

    monkeypatch.setattr(provider, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(provider, "validate_model", AsyncMock(return_value=True))
    chunks = [c async for c in provider.stream([ChatMessage(role="user", content="hi")], "openai/gpt-oss-20b")]
    assert chunks[0].content == "x" and seen["reasoning_effort"] == "low"

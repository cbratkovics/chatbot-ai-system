"""Failover chain: which errors trigger a fallback, and what gets recorded."""

from typing import List

import pytest

from chatbot_ai_system.providers.base import (
    AuthenticationError,
    BaseProvider,
    ChatMessage,
    ChatResponse,
    ContentFilterError,
    ModelNotFoundError,
    ProviderError,
    QuotaExceededError,
    RateLimitError,
    TimeoutError,
)
from chatbot_ai_system.providers.chain import ChainExhaustedError, ProviderChain, should_failover


class FakeProvider(BaseProvider):
    def __init__(self, name: str, error: Exception = None):
        super().__init__(api_key="x", timeout=1, max_retries=1)
        self.name = name
        self.error = error
        self.calls = 0

    async def chat(self, messages, model, temperature=0.7, max_tokens=None, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return ChatResponse(content=f"from {self.name}", model=model, provider=self.name)

    async def stream(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    async def validate_model(self, model: str) -> bool:  # pragma: no cover
        return True

    def get_supported_models(self) -> List[str]:  # pragma: no cover
        return []


def make_chain(providers: dict, fallbacks=(("groq", "llama-3.1-8b-instant"),)):
    def factory(name):
        if name not in providers:
            raise AuthenticationError(f"{name} key missing", provider=name, status_code=401)
        return providers[name]

    return ProviderChain(make_provider=factory, fallbacks=fallbacks)


MESSAGES = [ChatMessage(role="user", content="hi")]


@pytest.mark.asyncio
async def test_primary_success_records_single_ok_attempt():
    openai = FakeProvider("openai")
    chain = make_chain({"openai": openai, "groq": FakeProvider("groq")})
    response, attempts = await chain.complete(MESSAGES, "gpt-4o-mini")
    assert response.provider == "openai"
    assert [a.outcome for a in attempts] == ["ok"]
    assert attempts[0].provider == "openai" and attempts[0].model == "gpt-4o-mini"


@pytest.mark.parametrize(
    "error",
    [
        AuthenticationError("bad key", provider="openai", status_code=401),
        QuotaExceededError("no credits", provider="openai", status_code=402),
        RateLimitError("slow down", provider="openai"),
        ProviderError("upstream 503", provider="openai", status_code=503),
        ProviderError("connection reset", provider="openai", status_code=None),
        TimeoutError("timed out", provider="openai"),
        ModelNotFoundError("gone", provider="openai", status_code=404),
    ],
)
@pytest.mark.asyncio
async def test_failover_triggers(error):
    openai = FakeProvider("openai", error)
    groq = FakeProvider("groq")
    chain = make_chain({"openai": openai, "groq": groq})
    response, attempts = await chain.complete(MESSAGES, "gpt-4o-mini")
    assert response.provider == "groq"
    assert [a.outcome for a in attempts] == ["failed", "ok"]
    assert attempts[0].provider == "openai" and attempts[0].error_code
    assert attempts[1].model == "llama-3.1-8b-instant"
    assert groq.calls == 1


@pytest.mark.asyncio
async def test_client_side_4xx_does_not_failover():
    openai = FakeProvider("openai", ContentFilterError("blocked", provider="openai", status_code=400))
    groq = FakeProvider("groq")
    chain = make_chain({"openai": openai, "groq": groq})
    with pytest.raises(ContentFilterError):
        await chain.complete(MESSAGES, "gpt-4o-mini")
    assert groq.calls == 0


@pytest.mark.asyncio
async def test_unconfigured_fallback_is_skipped_and_primary_error_reported():
    openai = FakeProvider("openai", QuotaExceededError("no credits", provider="openai", status_code=402))
    chain = make_chain({"openai": openai})  # groq has no key
    with pytest.raises(ChainExhaustedError) as excinfo:
        await chain.complete(MESSAGES, "gpt-4o-mini")
    err = excinfo.value
    assert isinstance(err.primary_error, QuotaExceededError)
    assert [a.outcome for a in err.attempts] == ["failed", "skipped"]
    assert err.attempts[1].error_code == "auth_error"


@pytest.mark.asyncio
async def test_unknown_model_raises_model_not_found():
    chain = make_chain({"openai": FakeProvider("openai")}, fallbacks=())
    with pytest.raises(ModelNotFoundError):
        await chain.complete(MESSAGES, "not-a-model")


def test_should_failover_matrix():
    assert should_failover(RateLimitError("x")) is True
    assert should_failover(ProviderError("x", status_code=500)) is True
    assert should_failover(ProviderError("x", status_code=None)) is True
    assert should_failover(ProviderError("x", status_code=400)) is False
    assert should_failover(ContentFilterError("x", status_code=400)) is False


def test_legacy_model_ids_resolve_to_current_models():
    from chatbot_ai_system.providers.catalog import provider_for, resolve_model

    assert resolve_model("gpt-3.5-turbo") == "gpt-4o-mini"
    assert resolve_model("gpt-4o-mini") == "gpt-4o-mini"
    assert resolve_model("made-up") == "made-up"
    assert provider_for(resolve_model("claude-3-haiku-20240307")) == "anthropic"


def test_route_accepts_legacy_model_id(client):
    res = client.post(
        "/api/v1/chat/completions",
        json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "hi"}]},
    )
    # No real key in tests: the chain is exhausted, but the model resolved (not a 404).
    assert res.status_code != 404
    body = res.json()
    assert body["error"]["attempts"][0]["model"] == "gpt-4o-mini"

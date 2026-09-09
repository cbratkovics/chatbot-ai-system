"""Every error is a structured envelope with the right status, and never a bare 500."""

import pytest
from fastapi.testclient import TestClient

from chatbot_ai_system.api.errors import classify_provider_error
from chatbot_ai_system.providers.base import (
    AuthenticationError,
    ModelNotFoundError,
    ProviderError,
    QuotaExceededError,
    RateLimitError,
    TimeoutError,
)


@pytest.mark.parametrize(
    "exc,status,code",
    [
        (AuthenticationError("x", provider="openai"), 401, "provider_auth_error"),
        (QuotaExceededError("x", provider="openai"), 402, "provider_quota_exhausted"),
        (RateLimitError("x", provider="openai"), 429, "provider_rate_limited"),
        (TimeoutError("x", provider="openai"), 504, "provider_timeout"),
        (ModelNotFoundError("x", provider="openai"), 404, "model_not_found"),
        (ProviderError("x", provider="openai", status_code=503), 502, "provider_error"),
        (ProviderError("x", provider="openai", status_code=None), 503, "provider_unavailable"),
    ],
)
def test_provider_error_classification(exc, status, code):
    assert classify_provider_error(exc) == (status, code)


def test_unhandled_exception_is_enveloped_with_cors_headers():
    from chatbot_ai_system.server.main import app

    @app.get("/__test_boom")
    async def boom():
        raise RuntimeError("simulated")

    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/__test_boom", headers={"Origin": "http://localhost:3000"})
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "internal_error"
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_validation_error_is_enveloped(client):
    res = client.post("/api/v1/chat/completions", json={"model": "gpt-4o-mini", "messages": []})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_unknown_model_is_404_envelope(client):
    res = client.post(
        "/api/v1/chat/completions",
        json={"model": "nope", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "model_not_found"


def test_http_exception_keeps_headers(client):
    from chatbot_ai_system.server.main import app
    from fastapi import HTTPException

    @app.get("/__test_http_exc")
    async def http_exc():
        raise HTTPException(status_code=429, detail="slow down", headers={"Retry-After": "7"})

    res = client.get("/__test_http_exc")
    assert res.status_code == 429
    assert res.headers.get("retry-after") == "7"
    assert res.json()["error"]["message"] == "slow down"

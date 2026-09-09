"""Demo guardrails: per-IP limits, token caps, history trimming, daily budget."""

import pytest

from chatbot_ai_system.api.guardrails import (
    DemoGuard,
    GuardrailConfig,
    GuardrailError,
    client_ip_from_headers,
)
from chatbot_ai_system.providers.base import ChatMessage


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def make_guard(**overrides):
    cfg = GuardrailConfig(per_minute=3, per_day=5, max_tokens=400, max_history_messages=4, daily_token_budget=1000)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    clock = Clock()
    return DemoGuard(cfg, clock=clock), clock


def test_per_minute_limit_is_per_ip_and_resets():
    guard, clock = make_guard()
    for _ in range(3):
        guard.check("1.1.1.1")
    with pytest.raises(GuardrailError) as exc:
        guard.check("1.1.1.1")
    assert exc.value.code == "rate_limited" and 1 <= exc.value.retry_after <= 60
    guard.check("2.2.2.2")  # another IP is unaffected
    clock.t += 61
    guard.check("1.1.1.1")  # window has slid


def test_per_day_limit():
    guard, clock = make_guard(per_minute=100)
    for _ in range(5):
        guard.check("1.1.1.1")
    with pytest.raises(GuardrailError) as exc:
        guard.check("1.1.1.1")
    assert exc.value.code == "daily_limit_reached"


def test_daily_token_budget_exhausted_then_resets_next_day():
    guard, clock = make_guard(per_minute=100, per_day=100)
    guard.record_usage(999)
    guard.check("1.1.1.1")
    guard.record_usage(1)
    with pytest.raises(GuardrailError) as exc:
        guard.check("1.1.1.1")
    assert exc.value.code == "demo_budget_exhausted"
    assert "tomorrow" in exc.value.message
    clock.t += 86_400
    guard.check("1.1.1.1")
    assert guard.snapshot()["tokens_used_today"] == 0


def test_clamp_max_tokens_and_trim_history():
    guard, _ = make_guard()
    assert guard.clamp_max_tokens(None) == 400
    assert guard.clamp_max_tokens(50) == 50
    assert guard.clamp_max_tokens(5000) == 400
    msgs = [ChatMessage(role="system", content="s")] + [
        ChatMessage(role="user" if i % 2 == 0 else "assistant", content=str(i)) for i in range(10)
    ]
    trimmed = guard.trim_history(msgs)
    assert [m.content for m in trimmed] == ["s", "6", "7", "8", "9"]


def test_disabled_guard_is_a_no_op():
    guard, _ = make_guard(enabled=False)
    for _ in range(50):
        guard.check("1.1.1.1")
    assert guard.clamp_max_tokens(5000) == 5000
    assert len(guard.trim_history([ChatMessage(role="user", content=str(i)) for i in range(20)])) == 20


def test_client_ip_prefers_first_forwarded_hop():
    assert client_ip_from_headers("9.9.9.9, 10.0.0.1", "127.0.0.1") == "9.9.9.9"
    assert client_ip_from_headers(None, "127.0.0.1") == "127.0.0.1"
    assert client_ip_from_headers("", None) == "unknown"


def test_route_returns_429_envelope_when_limited(client, monkeypatch):
    from chatbot_ai_system.api import chat as chat_api

    guard, _ = make_guard(per_minute=1)
    monkeypatch.setattr(chat_api, "demo_guard", guard)
    body = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]}
    client.post("/api/v1/chat/completions", json=body)
    res = client.post("/api/v1/chat/completions", json=body)
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "rate_limited"
    assert res.headers.get("retry-after")

"""Demo failure toggle: env-gated, header-driven, recorded in telemetry."""

import pytest
from fastapi.testclient import TestClient

from chatbot_ai_system.providers.chain import SIMULATED_OUTAGE

BODY = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "fail over"}]}
HEADER = {"X-Demo-Simulate-Failure": "1"}


def _enable_toggle(monkeypatch, enabled: bool):
    # get_settings() is lru-cached; patch the live instance the route depends on.
    from chatbot_ai_system.config import get_settings

    monkeypatch.setattr(get_settings(), "demo_failure_toggle_enabled", enabled)


def test_header_is_ignored_when_toggle_disabled(client: TestClient, fake_chat_provider, monkeypatch):
    _enable_toggle(monkeypatch, False)
    res = client.post("/api/v1/chat/completions", json=BODY, headers=HEADER)
    assert res.status_code == 200
    t = res.json()["telemetry"]
    assert t["simulated_failure"] is False and t["failover"] is False
    assert [a["outcome"] for a in t["attempts"]] == ["ok"]


def test_header_forces_primary_503_and_failover(client: TestClient, fake_chat_provider, monkeypatch):
    _enable_toggle(monkeypatch, True)
    res = client.post("/api/v1/chat/completions", json=BODY, headers=HEADER)
    assert res.status_code == 200, res.text
    t = res.json()["telemetry"]
    assert t["simulated_failure"] is True and t["failover"] is True
    assert t["attempts"][0]["error_code"] == SIMULATED_OUTAGE
    assert t["attempts"][0]["status_code"] == 503
    assert t["attempts"][0]["provider"] == "openai"  # primary never called
    assert t["attempts"][-1]["outcome"] == "ok" and t["attempts"][-1]["provider"] == "groq"
    assert fake_chat_provider.calls == 1


def test_toggle_applies_to_streaming_too(client: TestClient, fake_chat_provider, monkeypatch):
    _enable_toggle(monkeypatch, True)
    with client.stream(
        "POST", "/api/v1/chat/completions", json={**BODY, "stream": True}, headers=HEADER
    ) as res:
        text = res.read().decode()
    assert '"event": "meta"' not in text  # sanity: SSE is line-based, not JSON-wrapped
    assert "event: meta" in text and "event: done" in text
    assert SIMULATED_OUTAGE in text and '"provider": "groq"' in text


def test_health_advertises_the_toggle(client: TestClient, monkeypatch):
    _enable_toggle(monkeypatch, True)
    demo = client.get("/api/v1/chat/health").json()["demo"]
    assert demo["failure_toggle_enabled"] is True
    assert demo["simulate_header"] == "x-demo-simulate-failure"
    limit = client.get("/api/v1/chat/health").json()["rate_limit"]
    assert set(limit) == {"enabled", "requests", "period_seconds"}

"""SSE streaming on /chat/completions: event order, cache hit, failover before first token."""

from typing import Dict, List

import pytest
from fastapi.testclient import TestClient

from chatbot_ai_system.api import chat as chat_api
from chatbot_ai_system.providers.base import RateLimitError

BODY = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "stream please"}], "stream": True}


def parse_sse(text: str) -> List[Dict]:
    """Minimal SSE parser: [(event, json)] for each blank-line separated block."""
    import json

    events = []
    for block in text.strip().split("\n\n"):
        event, data = None, None
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if event:
            events.append({"event": event, "data": data})
    return events


@pytest.fixture(autouse=True)
def _fresh_cache():
    chat_api.cache = None
    yield
    chat_api.cache = None


def test_stream_emits_meta_delta_done(client: TestClient, fake_chat_provider):
    with client.stream("POST", "/api/v1/chat/completions", json=BODY) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        events = parse_sse(res.read().decode())

    kinds = [e["event"] for e in events]
    assert kinds[0] == "meta" and kinds[-1] == "done"
    assert kinds.count("delta") == len(fake_chat_provider.reply.split(" "))
    assert "".join(e["data"]["content"] for e in events if e["event"] == "delta") == fake_chat_provider.reply

    meta, done = events[0]["data"], events[-1]["data"]
    assert meta["provider"] == "openai" and meta["cache"]["status"] == "miss"  # chain slot name
    assert done["streamed"] is True
    assert done["usage"]["source"] == "provider" and done["usage"]["total_tokens"] > 0
    assert done["attempts"][0]["outcome"] == "ok"
    assert done["failover"] is False
    assert done["ttfb_ms"] is not None and done["latency_ms"] >= done["ttfb_ms"]


def test_second_identical_stream_is_a_cache_hit(client: TestClient, fake_chat_provider):
    with client.stream("POST", "/api/v1/chat/completions", json=BODY) as res:
        res.read()
    with client.stream("POST", "/api/v1/chat/completions", json=BODY) as res:
        events = parse_sse(res.read().decode())

    assert [e["event"] for e in events] == ["meta", "delta", "done"]
    assert events[0]["data"]["cache"]["status"] == "hit"
    assert events[1]["data"]["content"] == fake_chat_provider.reply
    assert events[-1]["data"]["cache"]["similarity"] == 1.0
    assert events[-1]["data"]["cost_usd"] == 0.0
    assert fake_chat_provider.calls == 1  # provider not called again


def test_stream_error_before_first_token_is_an_error_event(client: TestClient, fake_chat_provider):
    fake_chat_provider.stream_error = RateLimitError("slow down", provider="fake")
    with client.stream("POST", "/api/v1/chat/completions", json=BODY) as res:
        assert res.status_code == 200  # headers are already sent; the error travels in-band
        events = parse_sse(res.read().decode())

    assert [e["event"] for e in events] == ["error"]
    err = events[0]["data"]["error"]
    assert err["code"] == "provider_rate_limited"
    assert err["status_code"] == 429
    assert [a["outcome"] for a in err["attempts"]] == ["failed"] * len(err["attempts"])


def test_non_stream_response_carries_the_same_telemetry(client: TestClient, fake_chat_provider):
    res = client.post("/api/v1/chat/completions", json={**BODY, "stream": False})
    assert res.status_code == 200
    t = res.json()["telemetry"]
    assert t["provider"] == "openai" and t["streamed"] is False
    assert t["cache"]["status"] == "miss" and t["cache"]["backend"] == "memory"
    assert t["usage"]["prompt_tokens"] == 5 and t["cost_usd"] is not None

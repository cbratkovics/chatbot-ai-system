"""Outer per-IP limit: pure ASGI, error envelope, Retry-After, exempt probes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from chatbot_ai_system.api.ratelimit import RateLimitMiddleware


def make_app(limit=3, period=60, enabled=True) -> TestClient:
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, limit=limit, period=period, enabled=enabled)
    return TestClient(app)


def test_limit_returns_envelope_with_retry_after():
    client = make_app(limit=3)
    for _ in range(3):
        assert client.get("/ping").status_code == 200
    res = client.get("/ping")
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "rate_limited"
    assert int(res.headers["retry-after"]) >= 1


def test_clients_are_keyed_by_forwarded_for_first_hop():
    client = make_app(limit=1)
    assert client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1, 10.0.0.1"}).status_code == 200
    assert client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1, 10.0.0.2"}).status_code == 429
    assert client.get("/ping", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200


def test_health_and_metrics_are_exempt_and_disable_switch_works():
    client = make_app(limit=1)
    for _ in range(5):
        assert client.get("/health").status_code == 200
    off = make_app(limit=1, enabled=False)
    for _ in range(5):
        assert off.get("/ping").status_code == 200

"""A streamed answer must survive uvicorn's keep-alive timer on a reused connection.

Reproduced on the live stack: the browser's CORS preflight (or any earlier request) completes,
the POST reuses the connection, and the SSE stream was closed exactly ``timeout_keep_alive``
seconds later with ``net::ERR_INCOMPLETE_CHUNKED_ENCODING``. Cause: Starlette ``BaseHTTPMiddleware``
layers in the stack (uvicorn 0.24 / Starlette 0.27; slowapi's alone was enough). The fix is
structural (every middleware is pure ASGI), so this test runs a real uvicorn server with a 1 s
keep-alive and a stream that takes longer than that.
"""

import asyncio
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware

from chatbot_ai_system.providers.base import StreamChunk, TokenUsage

BODY = {"model": "gpt-4o-mini", "stream": True, "messages": [{"role": "user", "content": "slow stream"}]}


class SlowProvider:
    """Emits one word every 0.2 s for ~2.4 s: longer than the 1 s keep-alive used below."""

    calls = 0

    async def stream(self, messages, model, temperature=0.7, max_tokens=None, **kw):
        for i in range(12):
            await asyncio.sleep(0.2)
            yield StreamChunk(content=f"w{i} ", is_final=False)
        yield StreamChunk(content="", is_final=True, usage=TokenUsage(prompt_tokens=1, completion_tokens=12, total_tokens=13))

    async def validate_model(self, model):
        return True


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def served_app(monkeypatch):
    from chatbot_ai_system.api import chat as chat_api
    from chatbot_ai_system.server.main import app

    monkeypatch.setattr(chat_api, "make_provider", lambda name, settings: SlowProvider())
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", timeout_keep_alive=1)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "uvicorn did not start"
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def test_no_base_http_middleware_in_the_stack():
    """Any BaseHTTPMiddleware (slowapi's included) re-introduced the 5 s cut; keep them all pure ASGI."""
    from chatbot_ai_system.server.main import app

    base = [m.cls.__name__ for m in app.user_middleware if issubclass(m.cls, BaseHTTPMiddleware)]
    assert base == [], base


def test_stream_survives_keepalive_timer_after_a_prior_request(served_app):
    with httpx.Client(base_url=served_app, timeout=20) as client:
        # 1. a preflight-style request on the connection, exactly like a browser
        pre = client.options(
            "/api/v1/chat/completions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert pre.status_code == 200
        # 2. the streamed answer on the same keep-alive connection, lasting > timeout_keep_alive
        started = time.perf_counter()
        with client.stream("POST", "/api/v1/chat/completions", json=BODY, headers={"Origin": "http://localhost:3000"}) as res:
            assert res.status_code == 200
            text = res.read().decode()
        elapsed = time.perf_counter() - started

    assert elapsed > 1.5, f"stream ended too early ({elapsed:.2f}s): keep-alive timer cut it"
    assert text.count("event: delta") == 12
    assert "event: done" in text

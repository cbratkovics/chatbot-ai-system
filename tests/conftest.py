"""Pytest configuration and fixtures."""

import os
import sys

# Set test environment before any imports
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:test123@localhost:5432/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")

import asyncio
from typing import AsyncIterator, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient


def pytest_runtest_setup(item):
    """Skip @pytest.mark.live tests unless their external service is configured.

    ``@pytest.mark.live("TEST_BASE_URL")`` names the env var that carries the service
    address. Nothing in the test run starts a server; you point it at one.
    """
    for marker in item.iter_markers("live"):
        env_var = marker.args[0] if marker.args else "TEST_BASE_URL"
        if not os.environ.get(env_var):
            pytest.skip(f"live test: set {env_var} to run it")


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Ensure test environment is properly configured."""
    os.environ["ENVIRONMENT"] = "test"
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = "postgresql://postgres:test123@localhost:5432/test_db"
    if "REDIS_URL" not in os.environ:
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"
    yield
    # Cleanup if needed


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"


@pytest.fixture
def mock_settings():
    """Provide mock settings for tests."""
    from chatbot_ai_system.config.settings import Settings

    return Settings(
        database_url="sqlite:///test.db",
        redis_url="redis://localhost:6379/1",
        jwt_secret_key="test-secret-key",
    )


@pytest.fixture
def client():
    from chatbot_ai_system.server.main import app

    return TestClient(app)


@pytest_asyncio.fixture
async def async_client():
    """Async test client fixture."""
    from chatbot_ai_system.server.main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def _reset_chat_singletons():
    """Fresh demo guardrails per test so per-IP limits never leak between tests."""
    from chatbot_ai_system.api import chat as chat_api

    chat_api.demo_guard = None
    yield
    chat_api.demo_guard = None


@pytest.fixture
def mock_redis():
    """In-memory stand-in for redis.asyncio with TTL, SCAN, and pipeline semantics.

    Tests may still override individual methods (e.g. ``mock_redis.get = AsyncMock(...)``).
    """
    import fnmatch
    import time as _time

    redis = MagicMock()
    redis._data = {}
    redis._expiry = {}

    def _alive(key):
        exp = redis._expiry.get(key)
        if exp is not None and exp <= _time.time():
            redis._data.pop(key, None)
            redis._expiry.pop(key, None)
            return False
        return key in redis._data

    async def mock_get(key):
        return redis._data.get(key) if _alive(key) else None

    async def mock_setex(key, ttl, value):
        redis._data[key] = value
        redis._expiry[key] = _time.time() + ttl
        return True

    async def mock_set(key, value, *args, **kwargs):
        redis._data[key] = value
        redis._expiry.pop(key, None)
        return True

    async def mock_expire(key, ttl):
        if key in redis._data:
            redis._expiry[key] = _time.time() + ttl
        return True

    async def mock_delete(*keys):
        removed = 0
        for key in keys:
            if key in redis._data:
                del redis._data[key]
                redis._expiry.pop(key, None)
                removed += 1
        return removed

    async def mock_scan_iter(match="*", **kwargs):
        for key in list(redis._data):
            if _alive(key) and fnmatch.fnmatch(key, match):
                yield key

    def mock_pipeline(*args, **kwargs):
        pipe = MagicMock()
        queued = []
        pipe.setex = MagicMock(side_effect=lambda k, ttl, v: queued.append(("setex", k, ttl, v)))
        pipe.set = MagicMock(side_effect=lambda k, v: queued.append(("set", k, None, v)))

        async def execute():
            for op, k, ttl, v in queued:
                await (mock_setex(k, ttl, v) if op == "setex" else mock_set(k, v))
            return [True] * len(queued)

        pipe.execute = AsyncMock(side_effect=execute)
        return pipe

    redis.get = AsyncMock(side_effect=mock_get)
    redis.set = AsyncMock(side_effect=mock_set)
    redis.setex = AsyncMock(side_effect=mock_setex)
    redis.delete = AsyncMock(side_effect=mock_delete)
    redis.expire = AsyncMock(side_effect=mock_expire)
    redis.scan_iter = mock_scan_iter
    redis.zrange = AsyncMock(return_value=[])
    redis.zadd = AsyncMock()
    redis.hget = AsyncMock(return_value=None)
    redis.hset = AsyncMock()
    redis.flushdb = AsyncMock()
    redis.info = AsyncMock(return_value={})
    redis.ttl = AsyncMock(return_value=3600)
    redis.bgsave = AsyncMock(return_value=True)
    redis.zcount = AsyncMock(return_value=0)
    redis.eval = AsyncMock(return_value=1)
    redis.pipeline = MagicMock(side_effect=mock_pipeline)
    return redis


@pytest.fixture
def mock_database():
    """AsyncSession stand-in: every awaited method is an AsyncMock."""
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock())  # awaited -> sync Result-like object
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.rollback = AsyncMock()
    db.begin = MagicMock(return_value=AsyncMock())
    return db


class FakeChatProvider:
    """Deterministic provider for the HTTP and WebSocket chat paths (no network)."""

    name = "fake"

    def __init__(self, reply: str = "fake response") -> None:
        self.reply = reply
        self.calls = 0
        self.stream_error: Exception | None = None  # raise this instead of streaming

    async def chat(self, messages, model, temperature=0.7, max_tokens=None, **kwargs):
        from chatbot_ai_system.providers.base import ChatResponse

        self.calls += 1
        return ChatResponse(
            content=self.reply,
            model=model,
            provider="fake",
            finish_reason="stop",
            usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        )

    async def stream_chat(self, messages, model, temperature=0.7, max_tokens=None, **kwargs):
        from types import SimpleNamespace

        self.calls += 1
        for word in self.reply.split(" "):
            yield SimpleNamespace(content=word + " ", is_final=False)

    async def stream(self, messages, model, temperature=0.7, max_tokens=None, **kwargs):
        """Chain-facing stream: content chunks, then a final chunk carrying usage."""
        from chatbot_ai_system.providers.base import StreamChunk, TokenUsage

        self.calls += 1
        if self.stream_error is not None:
            raise self.stream_error
        words = self.reply.split(" ")
        for i, word in enumerate(words):
            yield StreamChunk(content=word + (" " if i < len(words) - 1 else ""), is_final=False)
        yield StreamChunk(
            content="",
            is_final=True,
            usage=TokenUsage(prompt_tokens=5, completion_tokens=len(words), total_tokens=5 + len(words)),
        )

    async def validate_model(self, model: str) -> bool:
        return True

    def get_supported_models(self):
        return []


@pytest.fixture
def fake_chat_provider(monkeypatch):
    """Route /api/v1/chat/completions and /ws/chat to FakeChatProvider.

    Combined with the memory-cache fallback this makes the app fully healthy under test
    with no Redis and no provider keys.
    """
    from chatbot_ai_system.api import chat as chat_api
    from chatbot_ai_system.api import websocket as ws_api

    provider = FakeChatProvider()
    monkeypatch.setattr(chat_api, "make_provider", lambda name, settings: provider)
    monkeypatch.setattr(
        ws_api.ProviderFactory, "create_streaming_provider", lambda model, settings: provider
    )
    return provider


def _fake_openai_like_response(model: str, messages: list, prefix: str) -> dict:
    users = [m.get("content", "") for m in messages if m.get("role") == "user"]
    content = f"{prefix}: " + " | ".join(users)
    return {
        "id": "fake-id",
        "object": "chat.completion",
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


@pytest.fixture
def fake_core_clients(monkeypatch):
    """Give the core/models providers fake SDK clients instead of real OpenAI/Anthropic ones.

    The fake echoes the user messages back so context-preservation assertions hold.
    """
    from chatbot_ai_system.core.models import anthropic_provider, openai_provider

    openai_client = MagicMock()
    openai_client.chat.completions.create = AsyncMock(
        side_effect=lambda **kw: _fake_openai_like_response(
            kw.get("model", "gpt"), kw.get("messages", []), "fake-openai"
        )
    )
    anthropic_client = MagicMock()
    anthropic_client.messages.create = AsyncMock(
        side_effect=lambda **kw: _fake_openai_like_response(
            kw.get("model", "claude"), kw.get("messages", []), "fake-anthropic"
        )
    )
    monkeypatch.setattr(
        openai_provider.OpenAIProvider,
        "_init_client",
        lambda self: setattr(self, "client", openai_client),
    )
    monkeypatch.setattr(
        anthropic_provider.AnthropicProvider,
        "_init_client",
        lambda self: setattr(self, "client", anthropic_client),
    )
    return {"openai": openai_client, "anthropic": anthropic_client}


@pytest_asyncio.fixture
async def test_server():
    """Start test server for WebSocket tests."""
    import asyncio
    from uvicorn import Config, Server
    from chatbot_ai_system.server.main import app

    config = Config(app=app, host="127.0.0.1", port=8001, log_level="error")
    server = Server(config)

    # Create and start server task
    task = asyncio.create_task(server.serve())
    await asyncio.sleep(0.5)  # Let server start

    yield "http://127.0.0.1:8001"

    # Shutdown server
    server.should_exit = True
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.fixture
def mock_websocket():
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def mock_openai_client():
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock()
    return client


@pytest.fixture
def mock_anthropic_client():
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock()
    return client


@pytest.fixture
def mock_metrics_collector():
    collector = MagicMock()
    collector.increment_counter = MagicMock()
    collector.record_gauge = MagicMock()
    collector.record_latency = MagicMock()
    return collector


@pytest.fixture
def sample_chat_request():
    return {
        "messages": [{"role": "user", "content": "Hello"}],
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
    }


@pytest.fixture
def sample_chat_response():
    return {
        "id": "test-id",
        "choices": [{"message": {"content": "Hello!"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }


@pytest.fixture
def cache_config():
    return {"similarity_threshold": 0.85, "ttl_seconds": 3600, "max_entries": 1000}


@pytest.fixture
def tenant_config():
    return {
        "tenant_id": "tenant123",
        "tier": "enterprise",
        "status": "active",
        "rate_limits": {"requests_per_minute": 1000},
    }


@pytest.fixture
def chatbot_client():
    from chatbot_ai_system.sdk.client import ChatbotClient

    return ChatbotClient(api_key="test-key")


@pytest.fixture
def mock_stream_response():
    async def stream():
        for i in range(3):
            yield {"chunk": f"data_{i}"}

    return stream


@pytest_asyncio.fixture
async def async_http_client():
    """HTTP client for integration tests."""
    from chatbot_ai_system.server.main import app

    async with AsyncClient(app=app, base_url="http://localhost:8000") as client:
        yield client


@pytest.fixture
def auth_headers():
    """Authentication headers for tests."""
    return {
        "Authorization": "Bearer test-token",
        "X-API-Key": "test-api-key",
        "X-Tenant-ID": "test-tenant",
    }


@pytest_asyncio.fixture
async def test_server_websocket():
    """Start test server for integration tests."""
    import uvicorn
    from chatbot_ai_system.server.main import app

    # Start server in background
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)

    # Create task to run server
    task = asyncio.create_task(server.serve())

    # Wait for server to start
    await asyncio.sleep(1)

    yield

    # Shutdown server
    server.should_exit = True
    await task


@pytest_asyncio.fixture
async def db_session():
    """Database session for tests."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.rollback()

    await engine.dispose()


@pytest.fixture
def mock_model_factory():
    """Mock model factory."""
    factory = MagicMock()
    factory.create_model = MagicMock()
    factory.get_available_models = MagicMock(return_value=["gpt-3.5-turbo", "claude-3-opus"])
    return factory


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager."""
    manager = MagicMock()
    manager.get = AsyncMock(return_value=None)
    manager.set = AsyncMock()
    manager.invalidate = AsyncMock()
    manager.get_statistics = AsyncMock(return_value={"hit_rate": 0.7})
    return manager


@pytest.fixture
def mock_openai_provider():
    """Mock OpenAI provider to avoid real API calls."""
    with patch("chatbot_ai_system.providers.openai_provider.OpenAIProvider") as MockProvider:
        instance = MockProvider.return_value

        async def mock_generate(*args, **kwargs):
            return {
                "content": "This is a mocked OpenAI response",
                "model": kwargs.get("model", "gpt-3.5-turbo"),
                "provider": "openai",
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                "cached": False,
            }

        instance.generate = AsyncMock(side_effect=mock_generate)
        instance.generate_stream = AsyncMock()
        yield instance


@pytest.fixture
def mock_anthropic_provider():
    """Mock Anthropic provider to avoid real API calls."""
    with patch("chatbot_ai_system.providers.anthropic_provider.AnthropicProvider") as MockProvider:
        instance = MockProvider.return_value

        async def mock_generate(*args, **kwargs):
            return {
                "content": "This is a mocked Claude response",
                "model": kwargs.get("model", "claude-3-sonnet"),
                "provider": "anthropic",
                "usage": {"input_tokens": 10, "output_tokens": 20},
                "cached": False,
            }

        instance.generate = AsyncMock(side_effect=mock_generate)
        instance.generate_stream = AsyncMock()
        yield instance


@pytest.fixture
def mock_all_providers(mock_openai_provider, mock_anthropic_provider):
    """Mock all AI providers for comprehensive testing."""
    return {"openai": mock_openai_provider, "anthropic": mock_anthropic_provider}

"""Pytest configuration and fixtures."""

import asyncio
import os
import sys
from typing import AsyncIterator, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient


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


@pytest.fixture
def mock_redis():
    redis = MagicMock()
    # Store data in memory for testing
    redis._data = {}

    async def mock_get(key):
        return redis._data.get(key)

    async def mock_setex(key, ttl, value):
        redis._data[key] = value
        return True

    async def mock_set(key, value):
        redis._data[key] = value
        return True

    async def mock_delete(key):
        if key in redis._data:
            del redis._data[key]
        return 1

    redis.get = AsyncMock(side_effect=mock_get)
    redis.set = AsyncMock(side_effect=mock_set)
    redis.setex = AsyncMock(side_effect=mock_setex)
    redis.delete = AsyncMock(side_effect=mock_delete)
    redis.zrange = AsyncMock(return_value=[])
    redis.zadd = AsyncMock()
    redis.expire = AsyncMock()
    redis.hget = AsyncMock(return_value=None)
    redis.hset = AsyncMock()
    redis.flushdb = AsyncMock()
    redis.info = AsyncMock(return_value={})
    redis.ttl = AsyncMock(return_value=3600)
    redis.bgsave = AsyncMock(return_value=True)
    redis.zcount = AsyncMock(return_value=0)
    redis.eval = AsyncMock(return_value=1)
    redis.pipeline = MagicMock(return_value=MagicMock(execute=AsyncMock()))
    return redis


@pytest.fixture
def mock_database():
    db = MagicMock()
    db.execute = MagicMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.rollback = AsyncMock()
    return db


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


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Set up test environment variables."""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/15")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")


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

"""Cache fallback: no Redis -> in-process memory cache with the same interface."""

import pytest

from chatbot_ai_system.api import chat as chat_api
from chatbot_ai_system.cache.memory_cache import MemoryCache
from chatbot_ai_system.config.settings import Settings


def make_settings(**aliases):
    """Env-alias kwargs with dotenv disabled: explicit values must win over .env."""
    return Settings(_env_file=None, **aliases)


@pytest.fixture(autouse=True)
def _reset_cache_singletons():
    chat_api.cache = None
    chat_api.cache_key_generator = None
    yield
    chat_api.cache = None
    chat_api.cache_key_generator = None


@pytest.mark.asyncio
async def test_unset_redis_url_uses_memory_backend():
    settings = make_settings(REDIS_URL="", CACHE_ENABLED=True)
    backend = await chat_api.build_cache(settings)
    assert isinstance(backend, MemoryCache)
    assert backend.backend == "memory"


@pytest.mark.asyncio
async def test_unreachable_redis_falls_back_within_timeout():
    # Non-routable address: connect must fail fast (bounded by the connect timeout).
    settings = make_settings(
        REDIS_URL="redis://10.255.255.1:6379/0",
        CACHE_ENABLED=True,
        CACHE_CONNECT_TIMEOUT_SECONDS=0.5,
    )
    import time

    started = time.perf_counter()
    backend = await chat_api.build_cache(settings)
    elapsed = time.perf_counter() - started
    assert isinstance(backend, MemoryCache)
    assert elapsed < 5, f"fallback took {elapsed:.1f}s; connect timeout not honoured"


@pytest.mark.asyncio
async def test_cache_disabled_returns_none():
    settings = make_settings(CACHE_ENABLED=False)
    assert await chat_api.build_cache(settings) is None


@pytest.mark.asyncio
async def test_memory_cache_hit_miss_ttl_and_lru():
    cache = MemoryCache(ttl_seconds=60, max_entries=2)
    assert await cache.get_cached_response("k1") is None
    await cache.cache_response("k1", {"content": "one"})
    assert (await cache.get_cached_response("k1"))["content"] == "one"

    # TTL expiry
    await cache.cache_response("short", {"content": "x"}, ttl=-1)
    assert await cache.get_cached_response("short") is None

    # LRU eviction: k1 was touched, so k2 is the oldest when k3 arrives.
    await cache.cache_response("k2", {"content": "two"})
    await cache.get_cached_response("k1")
    await cache.cache_response("k3", {"content": "three"})
    assert await cache.get_cached_response("k2") is None
    assert await cache.get_cached_response("k1") is not None

    stats = await cache.get_stats()
    assert stats.hits >= 2 and stats.misses >= 2
    health = await cache.health_check()
    assert health["backend"] == "memory" and health["connected"] is True


@pytest.mark.asyncio
async def test_memory_cache_invalidate_pattern_and_clear():
    cache = MemoryCache()
    await cache.cache_response("chat:v1:gpt-4o-mini:aaa", {"content": 1})
    await cache.cache_response("chat:v1:gpt-4o:bbb", {"content": 2})
    assert await cache.invalidate_cache(pattern="chat:v1:gpt-4o-mini:*") == 1
    assert await cache.get_cached_response("chat:v1:gpt-4o:bbb") is not None
    assert await cache.clear_all() is True
    assert await cache.get_cached_response("chat:v1:gpt-4o:bbb") is None


def test_health_reports_cache_backend(client):
    body = client.get("/health").json()
    assert body["checks"]["cache"] in ("memory", "redis")

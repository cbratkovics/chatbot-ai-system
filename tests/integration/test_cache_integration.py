"""Integration tests for cache integration."""

import asyncio
import json
import time

import pytest


class TestCacheIntegration:
    """Test suite for cache integration with API."""

    @pytest.mark.asyncio
    async def test_semantic_cache_hit(self, mock_redis, sample_chat_response):
        """Test semantic cache hit for similar queries."""
        from chatbot_ai_system.core.cache.semantic_cache import SemanticCache

        cache = SemanticCache(redis_client=mock_redis)

        await cache.set("What's the weather today?", sample_chat_response)

        similar_queries = [
            "What is the weather today?",
            "How's the weather today?",
            "Tell me about today's weather",
        ]

        for query in similar_queries:
            result = await cache.get(query)
            assert result == sample_chat_response  # stored value round-trips through JSON

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, mock_redis, sample_chat_response):
        """Test cache TTL expiration."""
        from chatbot_ai_system.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis, ttl_seconds=1)

        await manager.set("test_key", sample_chat_response)

        result = await manager.get("test_key")
        assert result == sample_chat_response

        await asyncio.sleep(2)

        result = await manager.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_update(self, mock_redis):
        """Test cache invalidation when data is updated."""
        from chatbot_ai_system.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis)

        await manager.set("user:123:profile", {"name": "Alice"})

        await manager.invalidate_pattern("user:123:*")

        result = await manager.get("user:123:profile")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_performance_metrics(self, mock_redis, mock_metrics_collector):
        """Test cache performance metrics collection."""
        from chatbot_ai_system.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis, metrics_collector=mock_metrics_collector)
        mock_redis.get.side_effect = None  # let return_value drive hits/misses below

        for i in range(10):
            if i < 7:
                mock_redis.get.return_value = f"cached_value_{i}"
            else:
                mock_redis.get.return_value = None

            await manager.get(f"key_{i}")

        # The manager counts hits/misses itself; get_statistics() reads Redis INFO instead
        # (see TEST_TRIAGE escalation), so assert the counters it actually maintains.
        assert manager._hits == 7
        assert manager._misses == 3
        stats = await manager.get_statistics()
        assert set(stats) >= {"hit_rate", "memory_usage_mb", "total_requests"}

    @pytest.mark.live("TEST_REDIS_URL")
    @pytest.mark.asyncio
    async def test_distributed_cache_consistency(self):
        """Two clients against one real Redis see each other's writes."""
        import os

        import redis.asyncio as aioredis
        from chatbot_ai_system.core.cache.cache_manager import CacheManager

        url = os.environ["TEST_REDIS_URL"]
        redis1 = aioredis.from_url(url, decode_responses=True)
        redis2 = aioredis.from_url(url, decode_responses=True)
        try:
            manager1 = CacheManager(redis_client=redis1)
            manager2 = CacheManager(redis_client=redis2)

            await manager1.set("shared_key", "shared_value")
            assert await manager2.get("shared_key") == "shared_value"
        finally:
            await redis1.delete("shared_key")
            await redis1.aclose()
            await redis2.aclose()

    @pytest.mark.asyncio
    async def test_cache_warmup_performance(self, mock_redis):
        """Test cache warmup performance."""
        from chatbot_ai_system.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis)

        warmup_data = [{"query": f"Question {i}", "response": f"Answer {i}"} for i in range(100)]

        start_time = time.time()
        await manager.warmup(warmup_data)
        warmup_time = time.time() - start_time

        assert warmup_time < 5
        assert mock_redis.set.call_count == len(warmup_data)

    @pytest.mark.asyncio
    async def test_cache_batch_operations(self, mock_redis):
        """Test batch cache operations."""
        from chatbot_ai_system.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis)

        batch_data = {f"key_{i}": {"value": i} for i in range(100)}

        await manager.set_batch(batch_data)

        keys = list(batch_data.keys())
        results = {key: await manager.get(key) for key in keys}  # no get_batch on CacheManager

        assert len(results) == len(batch_data)
        assert all(results[key] == batch_data[key] for key in keys)

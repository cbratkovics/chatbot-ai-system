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
        from api.core.cache.semantic_cache import SemanticCache

        cache = SemanticCache(redis_client=mock_redis)

        await cache.set("What's the weather today?", sample_chat_response)

        similar_queries = [
            "What is the weather today?",
            "How's the weather today?",
            "Tell me about today's weather",
        ]

        for query in similar_queries:
            result = await cache.get(query)
            assert result is not None
            assert result["cached"] is True

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, mock_redis, sample_chat_response):
        """Test cache TTL expiration."""
        from api.core.cache.cache_manager import CacheManager

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
        from api.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis)

        await manager.set("user:123:profile", {"name": "Alice"})

        await manager.invalidate_pattern("user:123:*")

        result = await manager.get("user:123:profile")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_performance_metrics(self, mock_redis, mock_metrics_collector):
        """Test cache performance metrics collection."""
        from api.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis, metrics_collector=mock_metrics_collector)

        for i in range(10):
            if i < 7:
                mock_redis.get.return_value = f"cached_value_{i}"
            else:
                mock_redis.get.return_value = None

            await manager.get(f"key_{i}")

        stats = await manager.get_statistics()
        assert stats["hit_rate"] == 0.7

        mock_metrics_collector.record_gauge.assert_called()

    @pytest.mark.asyncio
    async def test_distributed_cache_consistency(self):
        """Test distributed cache consistency across instances."""
        import redis.asyncio as aioredis

        from api.core.cache.cache_manager import CacheManager

        redis1 = await aioredis.create_redis_pool("redis://localhost:6379/0")
        redis2 = await aioredis.create_redis_pool("redis://localhost:6379/0")

        manager1 = CacheManager(redis_client=redis1)
        manager2 = CacheManager(redis_client=redis2)

        await manager1.set("shared_key", {"data": "test"})

        result = await manager2.get("shared_key")
        assert result == {"data": "test"}

        redis1.close()
        redis2.close()

    @pytest.mark.asyncio
    async def test_cache_warmup_performance(self, mock_redis):
        """Test cache warmup performance."""
        from api.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis)

        warmup_data = [{"query": f"Question {i}", "response": f"Answer {i}"} for i in range(100)]

        start_time = time.time()
        await manager.warmup(warmup_data)
        warmup_time = time.time() - start_time

        assert warmup_time < 5
        assert mock_redis.set.call_count == len(warmup_data)

    @pytest.mark.asyncio
    async def test_cache_eviction_policy(self, mock_redis):
        """Test cache eviction policy."""
        from api.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis, max_size_mb=1, eviction_policy="lru")

        for i in range(1000):
            await manager.set(f"key_{i}", {"data": "x" * 1024})

        memory_usage = await manager.get_memory_usage()
        assert memory_usage <= 1.1

    @pytest.mark.asyncio
    async def test_cache_compression(self, mock_redis):
        """Test cache compression for large responses."""
        from api.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis, compression=True)

        large_response = {"text": "Large response text " * 1000, "metadata": {"size": "large"}}

        await manager.set("large_key", large_response)

        stored_size = len(mock_redis.set.call_args[0][1])
        original_size = len(json.dumps(large_response))

        assert stored_size < original_size * 0.5

    @pytest.mark.asyncio
    async def test_cache_batch_operations(self, mock_redis):
        """Test batch cache operations."""
        from api.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis)

        batch_data = {f"key_{i}": {"value": i} for i in range(100)}

        await manager.set_batch(batch_data)

        keys = list(batch_data.keys())
        results = await manager.get_batch(keys)

        assert len(results) == len(batch_data)
        assert all(key in results for key in keys)

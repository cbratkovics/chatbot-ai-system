"""Unit tests for cache service."""

import json
from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest


class TestSemanticCache:
    """Test suite for semantic cache functionality."""

    @pytest.mark.asyncio
    async def test_cache_initialization(self, mock_redis, cache_config):
        """Test cache service initialization."""
        from api.core.cache.semantic_cache import SemanticCache

        cache = SemanticCache(redis_client=mock_redis, config=cache_config)
        assert cache.redis_client == mock_redis
        assert cache.similarity_threshold == cache_config["similarity_threshold"]
        assert cache.ttl_seconds == cache_config["ttl_seconds"]

    @pytest.mark.asyncio
    async def test_embedding_generation(self, mock_redis, cache_config):
        """Test embedding generation for cache keys."""
        from api.core.cache.semantic_cache import SemanticCache

        with patch("api.core.cache.semantic_cache.generate_embedding") as mock_embed:
            mock_embed.return_value = np.random.rand(1536).tolist()

            cache = SemanticCache(redis_client=mock_redis, config=cache_config)
            query = "What is the weather?"
            embedding = await cache._generate_embedding(query)

            assert len(embedding) == 1536
            mock_embed.assert_called_once_with(query)

    @pytest.mark.asyncio
    async def test_similarity_calculation(self, mock_redis, cache_config):
        """Test cosine similarity calculation."""
        from api.core.cache.semantic_cache import SemanticCache

        cache = SemanticCache(redis_client=mock_redis, config=cache_config)

        vec1 = np.array([1, 0, 0])
        vec2 = np.array([1, 0, 0])
        similarity = cache._calculate_similarity(vec1, vec2)
        assert similarity == pytest.approx(1.0)

        vec3 = np.array([0, 1, 0])
        similarity = cache._calculate_similarity(vec1, vec3)
        assert similarity == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_cache_hit(self, mock_redis, cache_config, sample_chat_response):
        """Test cache hit scenario."""
        from api.core.cache.semantic_cache import SemanticCache

        cached_data = {
            "embedding": np.random.rand(1536).tolist(),
            "response": sample_chat_response,
            "timestamp": datetime.utcnow().isoformat(),
        }

        mock_redis.zrange.return_value = [json.dumps(cached_data).encode()]

        with patch("api.core.cache.semantic_cache.generate_embedding") as mock_embed:
            mock_embed.return_value = cached_data["embedding"]

            cache = SemanticCache(redis_client=mock_redis, config=cache_config)
            result = await cache.get("What is the weather?")

            assert result == sample_chat_response
            mock_redis.zrange.assert_called()

    @pytest.mark.asyncio
    async def test_cache_miss(self, mock_redis, cache_config):
        """Test cache miss scenario."""
        from api.core.cache.semantic_cache import SemanticCache

        mock_redis.zrange.return_value = []

        with patch("api.core.cache.semantic_cache.generate_embedding") as mock_embed:
            mock_embed.return_value = np.random.rand(1536).tolist()

            cache = SemanticCache(redis_client=mock_redis, config=cache_config)
            result = await cache.get("What is the weather?")

            assert result is None

    @pytest.mark.asyncio
    async def test_cache_set(self, mock_redis, cache_config, sample_chat_response):
        """Test setting cache entry."""
        from api.core.cache.semantic_cache import SemanticCache

        with patch("api.core.cache.semantic_cache.generate_embedding") as mock_embed:
            mock_embed.return_value = np.random.rand(1536).tolist()

            cache = SemanticCache(redis_client=mock_redis, config=cache_config)
            await cache.set("What is the weather?", sample_chat_response)

            mock_redis.zadd.assert_called()
            mock_redis.expire.assert_called()

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, mock_redis, cache_config):
        """Test cache invalidation."""
        from api.core.cache.semantic_cache import SemanticCache

        cache = SemanticCache(redis_client=mock_redis, config=cache_config)
        await cache.invalidate("test_key")

        mock_redis.delete.assert_called_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_ttl_management(self, mock_redis, cache_config):
        """Test TTL management for cache entries."""
        from api.core.cache.semantic_cache import SemanticCache

        mock_redis.ttl.return_value = 1800

        cache = SemanticCache(redis_client=mock_redis, config=cache_config)
        ttl = await cache.get_ttl("test_key")

        assert ttl == 1800
        mock_redis.ttl.assert_called_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_size_limit(self, mock_redis, cache_config):
        """Test cache size limit enforcement."""
        from api.core.cache.semantic_cache import SemanticCache

        cache = SemanticCache(redis_client=mock_redis, config=cache_config)
        cache.max_size_mb = 1

        large_data = {"data": "x" * (2 * 1024 * 1024)}

        with pytest.raises(ValueError, match="exceeds maximum cache size"):
            await cache.set("key", large_data)

    @pytest.mark.asyncio
    async def test_batch_cache_operations(self, mock_redis, cache_config):
        """Test batch cache operations."""
        from api.core.cache.semantic_cache import SemanticCache

        cache = SemanticCache(redis_client=mock_redis, config=cache_config)

        keys = ["key1", "key2", "key3"]
        values = [{"data": f"value{i}"} for i in range(3)]

        await cache.set_batch(keys, values)

        assert mock_redis.zadd.call_count == 3
        assert mock_redis.expire.call_count == 3


class TestCacheManager:
    """Test suite for cache manager."""

    @pytest.mark.asyncio
    async def test_manager_initialization(self, mock_redis):
        """Test cache manager initialization."""
        from api.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis)
        assert manager.redis_client == mock_redis
        assert manager.strategies is not None

    @pytest.mark.asyncio
    async def test_cache_strategy_selection(self, mock_redis):
        """Test cache strategy selection."""
        from api.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis)

        semantic_strategy = manager.get_strategy("semantic")
        assert semantic_strategy is not None

        standard_strategy = manager.get_strategy("standard")
        assert standard_strategy is not None

    @pytest.mark.asyncio
    async def test_cache_warmup(self, mock_redis):
        """Test cache warmup process."""
        from api.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis)

        warmup_data = [
            {"query": "What is AI?", "response": "AI is..."},
            {"query": "How does ML work?", "response": "ML works by..."},
        ]

        await manager.warmup(warmup_data)
        assert mock_redis.set.call_count >= len(warmup_data)

    @pytest.mark.asyncio
    async def test_cache_statistics(self, mock_redis):
        """Test cache statistics collection."""
        from api.core.cache.cache_manager import CacheManager

        mock_redis.info.return_value = {
            "used_memory": 1024000,
            "hits": 1000,
            "misses": 100,
            "evicted_keys": 10,
        }

        manager = CacheManager(redis_client=mock_redis)
        stats = await manager.get_statistics()

        assert stats["hit_rate"] == 0.9090909090909091
        assert stats["memory_usage_mb"] == pytest.approx(0.976, rel=0.01)

    @pytest.mark.asyncio
    async def test_cache_clear(self, mock_redis):
        """Test cache clearing."""
        from api.core.cache.cache_manager import CacheManager

        manager = CacheManager(redis_client=mock_redis)
        await manager.clear_all()

        mock_redis.flushdb.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_backup(self, mock_redis):
        """Test cache backup functionality."""
        from api.core.cache.cache_manager import CacheManager

        mock_redis.bgsave.return_value = True

        manager = CacheManager(redis_client=mock_redis)
        result = await manager.backup()

        assert result is True
        mock_redis.bgsave.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_restore(self, mock_redis):
        """Test cache restore functionality."""
        from api.core.cache.cache_manager import CacheManager

        backup_data = {"key1": "value1", "key2": "value2"}

        manager = CacheManager(redis_client=mock_redis)
        await manager.restore(backup_data)

        assert mock_redis.set.call_count == len(backup_data)

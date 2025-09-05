"""Integration tests for cache operations."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chatbot_ai_system.cache.redis_cache import RedisCache
from chatbot_ai_system.cache.semantic_cache import SemanticCache
from chatbot_ai_system.providers.base import ChatMessage, ChatResponse


@pytest.mark.integration
class TestCacheOperations:
    """Test cache operations integration."""

    @pytest.fixture
    async def redis_cache(self, mock_redis):
        """Create Redis cache instance with mock."""
        cache = RedisCache(redis_client=mock_redis)
        return cache

    @pytest.fixture
    async def semantic_cache(self, mock_redis):
        """Create semantic cache instance."""
        cache = SemanticCache(
            redis_client=mock_redis,
            similarity_threshold=0.85,
            max_cache_size=1000,
        )
        return cache

    @pytest.mark.asyncio
    async def test_basic_cache_hit_miss(self, redis_cache):
        """Test basic cache hit and miss scenarios."""
        # First request - cache miss
        messages = [ChatMessage(role="user", content="What is Python?")]
        cache_key = redis_cache.generate_cache_key(messages, "gpt-3.5-turbo")

        result = await redis_cache.get(cache_key)
        assert result is None  # Cache miss

        # Store response in cache
        response = ChatResponse(
            content="Python is a programming language",
            model="gpt-3.5-turbo",
            provider="openai",
            cached=False,
        )
        await redis_cache.set(cache_key, response, ttl=3600)

        # Second request - cache hit
        cached_result = await redis_cache.get(cache_key)
        assert cached_result is not None
        assert cached_result["content"] == response.content
        assert cached_result["cached"] is True  # Should be marked as cached

    @pytest.mark.asyncio
    async def test_semantic_cache_similarity(self, semantic_cache):
        """Test semantic caching with similar queries."""
        # Store initial response
        messages1 = [ChatMessage(role="user", content="What is Python?")]
        response1 = ChatResponse(
            content="Python is a high-level programming language",
            model="gpt-3.5-turbo",
            provider="openai",
            cached=False,
        )
        await semantic_cache.store(messages1, response1)

        # Query with similar meaning
        messages2 = [ChatMessage(role="user", content="Tell me about Python")]
        
        # Mock embedding similarity
        with patch.object(
            semantic_cache, "_calculate_similarity", return_value=0.90
        ):
            result = await semantic_cache.search(messages2)
            assert result is not None
            assert result["content"] == response1.content
            assert result["similarity_score"] == 0.90

        # Query with different meaning
        messages3 = [ChatMessage(role="user", content="What is Java?")]
        
        with patch.object(
            semantic_cache, "_calculate_similarity", return_value=0.60
        ):
            result = await semantic_cache.search(messages3)
            assert result is None  # Below threshold

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, redis_cache, mock_redis):
        """Test cache TTL expiration."""
        messages = [ChatMessage(role="user", content="Test query")]
        cache_key = redis_cache.generate_cache_key(messages, "gpt-3.5-turbo")

        response = ChatResponse(
            content="Test response",
            model="gpt-3.5-turbo",
            provider="openai",
            cached=False,
        )

        # Store with short TTL
        await redis_cache.set(cache_key, response, ttl=1)

        # Should be in cache immediately
        result = await redis_cache.get(cache_key)
        assert result is not None

        # Simulate expiration
        mock_redis._data.clear()

        # Should be expired
        result = await redis_cache.get(cache_key)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_invalidation_patterns(self, redis_cache):
        """Test cache invalidation patterns."""
        # Store multiple related cache entries
        base_messages = [ChatMessage(role="user", content="Base query")]
        
        for i in range(5):
            messages = base_messages + [
                ChatMessage(role="assistant", content=f"Response {i}")
            ]
            cache_key = redis_cache.generate_cache_key(messages, "gpt-3.5-turbo")
            response = ChatResponse(
                content=f"Response {i}",
                model="gpt-3.5-turbo",
                provider="openai",
                cached=False,
            )
            await redis_cache.set(cache_key, response)

        # Invalidate by pattern
        pattern = "*Base query*"
        invalidated = await redis_cache.invalidate_pattern(pattern)
        assert invalidated >= 5

        # All related entries should be gone
        for i in range(5):
            messages = base_messages + [
                ChatMessage(role="assistant", content=f"Response {i}")
            ]
            cache_key = redis_cache.generate_cache_key(messages, "gpt-3.5-turbo")
            result = await redis_cache.get(cache_key)
            assert result is None

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self, redis_cache):
        """Test concurrent cache read/write operations."""
        messages = [ChatMessage(role="user", content="Concurrent test")]
        cache_key = redis_cache.generate_cache_key(messages, "gpt-3.5-turbo")

        async def write_operation(index):
            response = ChatResponse(
                content=f"Response {index}",
                model="gpt-3.5-turbo",
                provider="openai",
                cached=False,
            )
            await redis_cache.set(f"{cache_key}_{index}", response)
            return index

        async def read_operation(index):
            result = await redis_cache.get(f"{cache_key}_{index}")
            return result is not None

        # Concurrent writes
        write_tasks = [write_operation(i) for i in range(10)]
        await asyncio.gather(*write_tasks)

        # Concurrent reads
        read_tasks = [read_operation(i) for i in range(10)]
        results = await asyncio.gather(*read_tasks)

        # All reads should succeed
        assert all(results)

    @pytest.mark.asyncio
    async def test_cache_compression(self, redis_cache):
        """Test cache compression for large responses."""
        # Create a large response
        large_content = "x" * 10000  # 10KB of data
        messages = [ChatMessage(role="user", content="Large response test")]
        cache_key = redis_cache.generate_cache_key(messages, "gpt-3.5-turbo")

        response = ChatResponse(
            content=large_content,
            model="gpt-3.5-turbo",
            provider="openai",
            cached=False,
        )

        # Enable compression
        redis_cache.compression_enabled = True
        redis_cache.compression_threshold = 1024  # 1KB

        # Store compressed
        await redis_cache.set(cache_key, response)

        # Retrieve and decompress
        result = await redis_cache.get(cache_key)
        assert result is not None
        assert result["content"] == large_content

    @pytest.mark.asyncio
    async def test_cache_warming(self, redis_cache):
        """Test cache warming functionality."""
        # Define common queries to warm
        common_queries = [
            [ChatMessage(role="user", content="What is AI?")],
            [ChatMessage(role="user", content="How does machine learning work?")],
            [ChatMessage(role="user", content="What is deep learning?")],
        ]

        # Warm cache with responses
        for i, messages in enumerate(common_queries):
            response = ChatResponse(
                content=f"Warmed response {i}",
                model="gpt-3.5-turbo",
                provider="openai",
                cached=False,
            )
            cache_key = redis_cache.generate_cache_key(messages, "gpt-3.5-turbo")
            await redis_cache.set(cache_key, response)

        # Verify all warmed entries are available
        for i, messages in enumerate(common_queries):
            cache_key = redis_cache.generate_cache_key(messages, "gpt-3.5-turbo")
            result = await redis_cache.get(cache_key)
            assert result is not None
            assert result["content"] == f"Warmed response {i}"

    @pytest.mark.asyncio
    async def test_cache_statistics_tracking(self, redis_cache):
        """Test cache statistics tracking."""
        # Reset statistics
        await redis_cache.reset_statistics()

        messages = [ChatMessage(role="user", content="Stats test")]
        cache_key = redis_cache.generate_cache_key(messages, "gpt-3.5-turbo")

        # Cache miss
        await redis_cache.get(cache_key)

        # Store response
        response = ChatResponse(
            content="Test response",
            model="gpt-3.5-turbo",
            provider="openai",
            cached=False,
        )
        await redis_cache.set(cache_key, response)

        # Cache hit
        await redis_cache.get(cache_key)
        await redis_cache.get(cache_key)

        # Get statistics
        stats = await redis_cache.get_statistics()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2/3

    @pytest.mark.asyncio
    async def test_multi_tenant_cache_isolation(self, redis_cache):
        """Test cache isolation between tenants."""
        messages = [ChatMessage(role="user", content="Tenant test")]
        
        # Store for tenant A
        cache_key_a = redis_cache.generate_cache_key(
            messages, "gpt-3.5-turbo", tenant_id="tenant_a"
        )
        response_a = ChatResponse(
            content="Response for tenant A",
            model="gpt-3.5-turbo",
            provider="openai",
            cached=False,
        )
        await redis_cache.set(cache_key_a, response_a)

        # Store for tenant B
        cache_key_b = redis_cache.generate_cache_key(
            messages, "gpt-3.5-turbo", tenant_id="tenant_b"
        )
        response_b = ChatResponse(
            content="Response for tenant B",
            model="gpt-3.5-turbo",
            provider="openai",
            cached=False,
        )
        await redis_cache.set(cache_key_b, response_b)

        # Retrieve for each tenant
        result_a = await redis_cache.get(cache_key_a)
        result_b = await redis_cache.get(cache_key_b)

        # Each tenant should get their own response
        assert result_a["content"] == "Response for tenant A"
        assert result_b["content"] == "Response for tenant B"
        assert cache_key_a != cache_key_b
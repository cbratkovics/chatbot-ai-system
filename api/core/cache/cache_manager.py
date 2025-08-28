"""Cache manager for handling multiple cache strategies and operations."""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages cache operations with multiple strategies."""

    def __init__(
        self,
        redis_client: aioredis.Redis,
        ttl_seconds: int = 3600,
        max_size_mb: int = 100,
        eviction_policy: str = "lru",
        compression: bool = False,
    ):
        """Initialize cache manager.

        Args:
            redis_client: Redis client instance
            ttl_seconds: Default TTL for cache entries
            max_size_mb: Maximum cache size in MB
            eviction_policy: Cache eviction policy
            compression: Enable compression for large values
        """
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
        self.max_size_mb = max_size_mb
        self.eviction_policy = eviction_policy
        self.compression = compression
        self.strategies = {}

        self._init_strategies()

    def _init_strategies(self):
        """Initialize cache strategies."""
        from .semantic_cache import SemanticCache

        self.strategies["semantic"] = SemanticCache(
            self.redis_client, {"ttl_seconds": self.ttl_seconds, "max_size_mb": self.max_size_mb}
        )
        self.strategies["standard"] = self

    def get_strategy(self, strategy_type: str):
        """Get cache strategy by type.

        Args:
            strategy_type: Type of cache strategy

        Returns:
            Cache strategy instance
        """
        return self.strategies.get(strategy_type, self)

    async def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if exists
        """
        try:
            value = await self.redis_client.get(key)
            if value:
                if self.compression:
                    import zlib

                    value = zlib.decompress(value)
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set cache value.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            Success status
        """
        try:
            serialized = json.dumps(value)

            if self.compression and len(serialized) > 1024:
                import zlib

                serialized = zlib.compress(serialized.encode())

            ttl = ttl or self.ttl_seconds
            await self.redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete cache entry.

        Args:
            key: Cache key

        Returns:
            Success status
        """
        try:
            result = await self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if exists
        """
        try:
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern.

        Args:
            pattern: Key pattern

        Returns:
            Number of deleted keys
        """
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Pattern invalidation error: {e}")
            return 0

    async def get_batch(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values from cache.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary of key-value pairs
        """
        try:
            values = await self.redis_client.mget(keys)
            result = {}

            for key, value in zip(keys, values, strict=False):
                if value:
                    try:
                        if self.compression:
                            import zlib

                            value = zlib.decompress(value)
                        result[key] = json.loads(value)
                    except Exception:
                        continue

            return result
        except Exception as e:
            logger.error(f"Batch get error: {e}")
            return {}

    async def set_batch(self, items: dict[str, Any], ttl: int | None = None) -> int:
        """Set multiple cache entries.

        Args:
            items: Dictionary of key-value pairs
            ttl: Time to live in seconds

        Returns:
            Number of successfully set items
        """
        success_count = 0

        for key, value in items.items():
            if await self.set(key, value, ttl):
                success_count += 1

        return success_count

    async def clear_all(self) -> bool:
        """Clear all cache entries.

        Returns:
            Success status
        """
        try:
            await self.redis_client.flushdb()
            return True
        except Exception as e:
            logger.error(f"Clear all error: {e}")
            return False

    async def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        try:
            info = await self.redis_client.info("stats")
            memory_info = await self.redis_client.info("memory")

            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total_requests = hits + misses

            return {
                "hit_rate": hits / total_requests if total_requests > 0 else 0,
                "hits": hits,
                "misses": misses,
                "memory_usage_mb": memory_info.get("used_memory", 0) / (1024 * 1024),
                "evicted_keys": info.get("evicted_keys", 0),
                "connected_clients": info.get("connected_clients", 0),
                "total_keys": await self.redis_client.dbsize(),
            }
        except Exception as e:
            logger.error(f"Statistics error: {e}")
            return {}

    async def warmup(self, data: list[dict[str, Any]]) -> int:
        """Warmup cache with predefined data.

        Args:
            data: List of cache entries

        Returns:
            Number of warmed entries
        """
        warmed = 0

        for entry in data:
            key = entry.get("key") or entry.get("query")
            value = entry.get("value") or entry.get("response")

            if key and value:
                if await self.set(key, value):
                    warmed += 1

        logger.info(f"Warmed {warmed} cache entries")
        return warmed

    async def backup(self) -> bool:
        """Trigger cache backup.

        Returns:
            Success status
        """
        try:
            await self.redis_client.bgsave()
            return True
        except Exception as e:
            logger.error(f"Backup error: {e}")
            return False

    async def restore(self, backup_data: dict[str, Any]) -> bool:
        """Restore cache from backup.

        Args:
            backup_data: Backup data to restore

        Returns:
            Success status
        """
        try:
            for key, value in backup_data.items():
                await self.set(key, value)
            return True
        except Exception as e:
            logger.error(f"Restore error: {e}")
            return False

    async def get_memory_usage(self) -> float:
        """Get current memory usage in MB.

        Returns:
            Memory usage in MB
        """
        try:
            memory_info = await self.redis_client.info("memory")
            return memory_info.get("used_memory", 0) / (1024 * 1024)
        except Exception as e:
            logger.error(f"Memory usage error: {e}")
            return 0.0

    async def enforce_size_limit(self) -> int:
        """Enforce cache size limit.

        Returns:
            Number of evicted keys
        """
        try:
            current_size = await self.get_memory_usage()

            if current_size > self.max_size_mb:
                if self.eviction_policy == "lru":
                    keys = await self.redis_client.keys("*")

                    key_scores = []
                    for key in keys[:100]:
                        idle_time = await self.redis_client.object("idletime", key)
                        key_scores.append((key, idle_time))

                    key_scores.sort(key=lambda x: x[1], reverse=True)

                    evicted = 0
                    for key, _ in key_scores[:10]:
                        await self.redis_client.delete(key)
                        evicted += 1

                        if await self.get_memory_usage() < self.max_size_mb * 0.9:
                            break

                    return evicted

            return 0
        except Exception as e:
            logger.error(f"Size limit enforcement error: {e}")
            return 0

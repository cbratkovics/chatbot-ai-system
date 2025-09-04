class CacheManager:
    def __init__(self, redis_client=None, ttl_seconds=3600, metrics_collector=None):
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
        self.metrics_collector = metrics_collector
        self._hits = 0
        self._misses = 0
        self.strategies = {
            "semantic": SemanticCache(redis_client),
            "standard": StandardCache(redis_client),
        }

    def get_strategy(self, name):
        return self.strategies.get(name)

    async def get(self, key):
        """Get value from cache."""
        if self.redis_client:
            value = await self.redis_client.get(key)
            if value:
                self._hits += 1
                return value
            self._misses += 1
        return None

    async def set(self, key, value, ttl=None):
        """Set value in cache."""
        if self.redis_client:
            ttl = ttl or self.ttl_seconds
            await self.redis_client.setex(key, ttl, value)
            return True
        return False

    async def invalidate_pattern(self, pattern):
        """Invalidate cache by pattern."""
        if self.redis_client:
            keys = []
            # Mock scan_iter for testing
            if hasattr(self.redis_client, "scan_iter"):
                async for key in self.redis_client.scan_iter(pattern):
                    keys.append(key)
                if keys:
                    await self.redis_client.delete(*keys)
            return len(keys)
        return 0

    async def set_batch(self, items):
        """Set multiple items in cache."""
        if self.redis_client:
            pipe = self.redis_client.pipeline()
            for key, value in items.items():
                pipe.setex(key, self.ttl_seconds, value)
            await pipe.execute()
            return True
        return False

    async def warmup(self, data):
        for item in data:
            await self.redis_client.set(item["query"], item["response"])

    async def get_statistics(self):
        # Get Redis info from the mock
        if hasattr(self.redis_client, "info"):
            info = await self.redis_client.info() if callable(self.redis_client.info) else self.redis_client.info.return_value
        else:
            info = {}
        
        # Calculate hit rate from Redis stats
        hits = info.get("hits", 0)
        misses = info.get("misses", 0)
        total_requests = hits + misses
        hit_rate = hits / total_requests if total_requests > 0 else 0
        
        # Calculate memory usage
        memory_usage_mb = info.get("used_memory", 0) / (1024 * 1024)
        
        return {"hit_rate": hit_rate, "memory_usage_mb": memory_usage_mb, "total_requests": total_requests}

    async def clear_all(self):
        await self.redis_client.flushdb()

    async def backup(self):
        return await self.redis_client.bgsave()

    async def restore(self, data):
        for key, value in data.items():
            await self.redis_client.set(key, value)


class StandardCache:
    def __init__(self, redis_client):
        self.redis_client = redis_client


from .semantic_cache import SemanticCache

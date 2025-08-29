"""Cache implementation using Redis."""

import hashlib
import json
from typing import Any

import redis.asyncio as redis

from chatbot_ai_system.config import settings


class CacheManager:
    """Manage caching with Redis."""

    def __init__(self):
        self._client = None

    async def connect(self):
        """Connect to Redis."""
        if not self._client and settings.redis_url:
            self._client = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

    async def disconnect(self):
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()

    def _generate_key(self, prefix: str, data: Any) -> str:
        """Generate cache key."""
        data_str = json.dumps(data, sort_keys=True)
        hash_key = hashlib.md5(data_str.encode()).hexdigest()
        return f"{prefix}:{hash_key}"

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if not self._client:
            return None

        try:
            value = await self._client.get(key)
            return json.loads(value) if value else None
        except Exception:
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """Set value in cache."""
        if not self._client:
            return False

        try:
            ttl = ttl or settings.cache_ttl_seconds
            await self._client.setex(
                key,
                ttl,
                json.dumps(value),
            )
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if not self._client:
            return False

        try:
            await self._client.delete(key)
            return True
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._client:
            return False

        try:
            return bool(await self._client.exists(key))
        except Exception:
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        if not self._client:
            return 0

        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                return await self._client.delete(*keys)
            return 0
        except Exception:
            return 0

    async def get_ttl(self, key: str) -> int | None:
        """Get TTL for a key."""
        if not self._client:
            return None

        try:
            ttl = await self._client.ttl(key)
            return ttl if ttl > 0 else None
        except Exception:
            return None

    async def cache_chat_response(
        self,
        messages: list,
        provider: str,
        model: str,
        response: str,
        ttl: int | None = None,
    ) -> bool:
        """Cache a chat response."""
        key = self._generate_key(f"chat:{provider}:{model}", {"messages": messages})
        return await self.set(key, response, ttl)

    async def get_cached_chat_response(
        self,
        messages: list,
        provider: str,
        model: str,
    ) -> str | None:
        """Get cached chat response."""
        key = self._generate_key(f"chat:{provider}:{model}", {"messages": messages})
        return await self.get(key)


# Global cache instance
cache = CacheManager()


__all__ = ["cache", "CacheManager"]

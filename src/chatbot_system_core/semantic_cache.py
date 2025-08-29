"""Simple semantic cache implementation."""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any


class SemanticCache:
    """Simple semantic cache for AI responses."""

    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize the semantic cache.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.cache: dict[str, dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds

    def _generate_key(self, prompt: str, provider: str | None = None) -> str:
        """Generate a cache key from prompt and provider."""
        content = f"{provider or 'default'}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get(self, prompt: str, provider: str | None = None) -> dict[str, Any] | None:
        """
        Get a cached response.

        Args:
            prompt: The prompt to look up
            provider: Optional provider name

        Returns:
            Cached response if found and not expired, None otherwise
        """
        key = self._generate_key(prompt, provider)

        if key in self.cache:
            entry = self.cache[key]
            if datetime.now() < entry["expires_at"]:
                return entry["response"]
            else:
                del self.cache[key]

        return None

    async def set(self, prompt: str, response: dict[str, Any], provider: str | None = None):
        """
        Cache a response.

        Args:
            prompt: The prompt that generated the response
            response: The response to cache
            provider: Optional provider name
        """
        key = self._generate_key(prompt, provider)
        self.cache[key] = {
            "response": response,
            "expires_at": datetime.now() + timedelta(seconds=self.ttl_seconds),
            "created_at": datetime.now(),
        }

    async def clear(self):
        """Clear all cache entries."""
        self.cache.clear()

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_entries = len(self.cache)
        expired_count = 0

        for key, entry in list(self.cache.items()):
            if datetime.now() >= entry["expires_at"]:
                expired_count += 1
                del self.cache[key]

        return {
            "total_entries": total_entries - expired_count,
            "expired_removed": expired_count,
            "memory_size_bytes": len(json.dumps(self.cache)),
        }

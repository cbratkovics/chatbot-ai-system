"""In-process LRU cache with the same public surface as :class:`RedisCache`.

Why: the demo must boot with no Redis. Same method names, same return shapes, so the
chat route does not care which backend it got. Exact-match keys only: hashing the
normalised prompt costs nothing and needs no ML dependency on the boot path.
"""

import fnmatch
import logging
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from .redis_cache import CacheStats

logger = logging.getLogger(__name__)


class MemoryCache:
    """Bounded LRU + TTL cache living in the worker process."""

    backend = "memory"

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 512) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._store: "OrderedDict[str, Tuple[float, Dict[str, Any]]]" = OrderedDict()
        self.stats = CacheStats()
        self._connected = True

    # -- lifecycle -------------------------------------------------------
    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False
        self._store.clear()

    # -- internals -------------------------------------------------------
    def _evict_expired(self, now: float) -> None:
        expired = [k for k, (exp, _) in self._store.items() if exp <= now]
        for k in expired:
            del self._store[k]

    # -- public API (mirrors RedisCache) --------------------------------
    async def get_cached_response(
        self, key: str, check_semantic: bool = False, semantic_threshold: float = 0.95
    ) -> Optional[Dict[str, Any]]:
        now = time.time()
        self.stats.total_requests += 1
        entry = self._store.get(key)
        if entry is None or entry[0] <= now:
            if entry is not None:
                del self._store[key]
            self.stats.misses += 1
            return None
        self._store.move_to_end(key)
        self.stats.hits += 1
        return entry[1]

    async def cache_response(
        self,
        key: str,
        response: Dict[str, Any],
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        now = time.time()
        self._evict_expired(now)
        self._store[key] = (now + (ttl or self.ttl_seconds), response)
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)
        return True

    async def invalidate_cache(
        self,
        key: Optional[str] = None,
        pattern: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        if key is not None:
            return 1 if self._store.pop(key, None) is not None else 0
        if pattern:
            doomed = [k for k in self._store if fnmatch.fnmatch(k, pattern)]
            for k in doomed:
                del self._store[k]
            return len(doomed)
        return 0

    async def warm_cache(self, common_queries: List[Dict[str, Any]]) -> int:
        count = 0
        for item in common_queries:
            if "key" in item and "response" in item:
                await self.cache_response(item["key"], item["response"], ttl=item.get("ttl"))
                count += 1
        return count

    async def get_stats(self) -> CacheStats:
        self.stats.calculate_hit_rate()
        self.stats.cache_size_bytes = len(self._store)
        return self.stats

    async def clear_all(self) -> bool:
        self._store.clear()
        return True

    async def health_check(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "backend": self.backend,
            "entries": len(self._store),
            "max_entries": self.max_entries,
            "stats": (await self.get_stats()).to_dict(),
        }

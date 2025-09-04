"""Cache module for the chatbot AI system."""

from typing import Optional

import redis.asyncio as redis_async

# Global redis client
redis_client: Optional[redis_async.Redis] = None


async def init_cache(redis_url: str):
    """Initialize Redis cache client."""
    global redis_client
    redis_client = await redis_async.from_url(redis_url, encoding="utf-8", decode_responses=True)
    return redis_client


async def close_cache():
    """Close Redis cache connection."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


# Import cache components
from .cache_manager import CacheManager
from .semantic_cache import SemanticCache

__all__ = [
    "redis_client",
    "init_cache",
    "close_cache",
    "CacheManager",
    "SemanticCache",
]

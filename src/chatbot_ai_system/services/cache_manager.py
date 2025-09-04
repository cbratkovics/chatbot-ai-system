"""Cache manager for the chatbot system."""
import json
import hashlib
import asyncio
from typing import Any, List, Optional, Dict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Manage caching operations."""
    
    def __init__(self, redis_client=None, **kwargs):
        """Initialize cache manager.
        
        Args:
            redis_client: Redis client instance
            **kwargs: Additional configuration options
        """
        self.redis_client = redis_client
        self.max_size_mb = kwargs.get('max_size_mb', 100)
        self.compression = kwargs.get('compression', False)
        self.compression_enabled = kwargs.get('compression_enabled', False)
        self.compression_threshold = kwargs.get('compression_threshold', 1024)
        self.eviction_policy = kwargs.get('eviction_policy', 'lru')
        self.ttl = kwargs.get('ttl', 3600)
        self.enabled = kwargs.get('enabled', True)
        self.semantic_cache_enabled = kwargs.get('semantic_cache_enabled', False)
        self.circuit_breaker_enabled = kwargs.get('cache_circuit_breaker_enabled', False)
        self.warming_enabled = kwargs.get('cache_warming_enabled', False)
        self._cache = {}  # In-memory fallback
        
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        if not self.enabled:
            return None
            
        try:
            if self.redis_client:
                value = await self.redis_client.get(key)
                if value:
                    return json.loads(value)
            else:
                # Fallback to in-memory cache
                entry = self._cache.get(key)
                if entry:
                    if entry['expires'] > datetime.now():
                        return entry['value']
                    else:
                        del self._cache[key]
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
            
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            Success status
        """
        if not self.enabled:
            return False
            
        ttl = ttl or self.ttl
        
        try:
            if self.redis_client:
                serialized = json.dumps(value)
                await self.redis_client.setex(key, ttl, serialized)
            else:
                # Fallback to in-memory cache
                self._cache[key] = {
                    'value': value,
                    'expires': datetime.now() + timedelta(seconds=ttl)
                }
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
            
    async def delete(self, key: str) -> bool:
        """Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Success status
        """
        try:
            if self.redis_client:
                await self.redis_client.delete(key)
            else:
                self._cache.pop(key, None)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
            
    async def clear(self, pattern: Optional[str] = None) -> bool:
        """Clear cache entries.
        
        Args:
            pattern: Pattern to match keys (None for all)
            
        Returns:
            Success status
        """
        try:
            if self.redis_client:
                if pattern:
                    keys = await self.redis_client.keys(pattern)
                    if keys:
                        await self.redis_client.delete(*keys)
                else:
                    await self.redis_client.flushdb()
            else:
                if pattern:
                    keys_to_delete = [k for k in self._cache.keys() if pattern in k]
                    for key in keys_to_delete:
                        del self._cache[key]
                else:
                    self._cache.clear()
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
            
    async def get_batch(self, keys: List[str]) -> List[Optional[Any]]:
        """Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            List of cached values (None for misses)
        """
        results = []
        for key in keys:
            result = await self.get(key)
            results.append(result)
        return results
        
    async def set_batch(self, items: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values in cache.
        
        Args:
            items: Dictionary of key-value pairs
            ttl: Time to live in seconds
            
        Returns:
            Success status
        """
        try:
            for key, value in items.items():
                await self.set(key, value, ttl)
            return True
        except Exception as e:
            logger.error(f"Batch set error: {e}")
            return False
            
    def generate_key(self, prefix: str, data: Any) -> str:
        """Generate cache key from data.
        
        Args:
            prefix: Key prefix
            data: Data to hash
            
        Returns:
            Cache key
        """
        data_str = json.dumps(data, sort_keys=True)
        hash_val = hashlib.md5(data_str.encode()).hexdigest()
        return f"{prefix}:{hash_val}"
        
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Cache statistics
        """
        try:
            if self.redis_client:
                info = await self.redis_client.info()
                return {
                    'hits': info.get('keyspace_hits', 0),
                    'misses': info.get('keyspace_misses', 0),
                    'keys': await self.redis_client.dbsize(),
                    'memory_used': info.get('used_memory_human', 'N/A')
                }
            else:
                return {
                    'hits': 0,
                    'misses': 0,
                    'keys': len(self._cache),
                    'memory_used': 'N/A'
                }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
            
    async def warm_cache(self, keys: List[str]) -> bool:
        """Warm cache with specific keys.
        
        Args:
            keys: List of keys to warm
            
        Returns:
            Success status
        """
        if not self.warming_enabled:
            return False
            
        # This is a placeholder - in production, you'd fetch data and cache it
        logger.info(f"Warming cache with {len(keys)} keys")
        return True
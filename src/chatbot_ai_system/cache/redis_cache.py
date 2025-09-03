"""
Redis cache implementation with connection pooling, compression, and circuit breaker.
"""

import gzip
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import orjson
from prometheus_client import Counter, Gauge, Histogram

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

logger = logging.getLogger(__name__)

# Prometheus metrics
cache_hits = Counter('cache_hits_total', 'Total number of cache hits')
cache_misses = Counter('cache_misses_total', 'Total number of cache misses')
cache_errors = Counter('cache_errors_total', 'Total number of cache errors')
cache_latency = Histogram('cache_latency_seconds', 'Cache operation latency')
cache_size = Gauge('cache_size_bytes', 'Total size of cached data')
cache_connections = Gauge('cache_connections_active', 'Number of active Redis connections')


@dataclass
class CacheStats:
    """Cache statistics tracking."""
    
    hits: int = 0
    misses: int = 0
    errors: int = 0
    total_requests: int = 0
    avg_latency_ms: float = 0.0
    cache_size_bytes: int = 0
    hit_rate: float = 0.0
    last_reset: datetime = field(default_factory=datetime.utcnow)
    
    def calculate_hit_rate(self):
        """Calculate cache hit rate."""
        if self.total_requests > 0:
            self.hit_rate = (self.hits / self.total_requests) * 100
        return self.hit_rate
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            **asdict(self),
            'last_reset': self.last_reset.isoformat(),
            'hit_rate': f"{self.hit_rate:.2f}%"
        }


class CircuitBreaker:
    """Circuit breaker pattern for Redis failures."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def record_success(self):
        """Record successful operation."""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def is_open(self) -> bool:
        """Check if circuit is open."""
        if self.state == "open":
            # Check if recovery timeout has passed
            if self.last_failure_time and \
               time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                logger.info("Circuit breaker entering half-open state")
                return False
            return True
        return False
    
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self.state == "half-open"


class RedisCache:
    """Redis cache with advanced features."""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        max_connections: int = 50,
        ttl_seconds: int = 3600,
        compression_threshold: int = 1000,
        enable_compression: bool = True,
        enable_circuit_breaker: bool = True
    ):
        """
        Initialize Redis cache.
        
        Args:
            redis_url: Redis connection URL
            max_connections: Maximum number of connections in pool
            ttl_seconds: Default TTL for cached items
            compression_threshold: Compress responses larger than this (bytes)
            enable_compression: Enable gzip compression
            enable_circuit_breaker: Enable circuit breaker pattern
        """
        self.redis_url = redis_url
        self.max_connections = max_connections
        self.ttl_seconds = ttl_seconds
        self.compression_threshold = compression_threshold
        self.enable_compression = enable_compression
        self.enable_circuit_breaker = enable_circuit_breaker
        
        self.client: Optional[redis.Redis] = None
        self.pool: Optional[ConnectionPool] = None
        self.stats = CacheStats()
        self.circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None
        self._connected = False
        
    async def connect(self):
        """Establish Redis connection with pooling."""
        try:
            # Create connection pool
            self.pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                decode_responses=False  # We handle encoding/decoding
            )
            
            # Create Redis client
            self.client = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            await self.client.ping()
            self._connected = True
            
            logger.info(f"Redis cache connected with {self.max_connections} max connections")
            
            if self.circuit_breaker:
                self.circuit_breaker.record_success()
                
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            raise
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            self._connected = False
            logger.info("Redis cache disconnected")
    
    def _should_compress(self, data: bytes) -> bool:
        """Check if data should be compressed."""
        return self.enable_compression and len(data) > self.compression_threshold
    
    def _compress_data(self, data: bytes) -> tuple[bytes, bool]:
        """Compress data if needed."""
        if self._should_compress(data):
            compressed = gzip.compress(data, compresslevel=1)  # Fast compression
            # Only use compression if it actually reduces size
            if len(compressed) < len(data):
                return compressed, True
        return data, False
    
    def _decompress_data(self, data: bytes, is_compressed: bool) -> bytes:
        """Decompress data if needed."""
        if is_compressed:
            return gzip.decompress(data)
        return data
    
    async def get_cached_response(
        self,
        key: str,
        check_semantic: bool = False,
        semantic_threshold: float = 0.95
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response.
        
        Args:
            key: Cache key
            check_semantic: Whether to check for semantic matches
            semantic_threshold: Similarity threshold for semantic matching
        
        Returns:
            Cached response or None
        """
        if not self._connected:
            logger.warning("Redis not connected, skipping cache lookup")
            return None
        
        # Check circuit breaker
        if self.circuit_breaker and self.circuit_breaker.is_open():
            logger.warning("Circuit breaker is open, skipping cache")
            cache_errors.inc()
            return None
        
        start_time = time.time()
        
        try:
            # Try exact match first
            data = await self.client.get(key)
            
            if data:
                # Get metadata
                metadata_key = f"{key}:meta"
                metadata = await self.client.get(metadata_key)
                
                is_compressed = False
                if metadata:
                    meta_dict = orjson.loads(metadata)
                    is_compressed = meta_dict.get("compressed", False)
                
                # Decompress if needed
                data = self._decompress_data(data, is_compressed)
                
                # Parse response
                response = orjson.loads(data)
                
                # Update stats
                self.stats.hits += 1
                self.stats.total_requests += 1
                cache_hits.inc()
                
                latency = time.time() - start_time
                cache_latency.observe(latency)
                
                logger.info(f"Cache hit for key: {key[:32]}...")
                
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()
                
                return response
            
            # If semantic matching is requested, search for similar keys
            if check_semantic:
                # This would require additional implementation with vector similarity
                # For now, we'll skip semantic matching
                pass
            
            # Cache miss
            self.stats.misses += 1
            self.stats.total_requests += 1
            cache_misses.inc()
            
            latency = time.time() - start_time
            cache_latency.observe(latency)
            
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.stats.errors += 1
            cache_errors.inc()
            
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            
            return None
    
    async def cache_response(
        self,
        key: str,
        response: Dict[str, Any],
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """
        Cache a response.
        
        Args:
            key: Cache key
            response: Response to cache
            ttl: TTL in seconds (uses default if not specified)
            tags: Optional tags for cache invalidation
        
        Returns:
            Success status
        """
        if not self._connected:
            logger.warning("Redis not connected, skipping cache write")
            return False
        
        # Check circuit breaker
        if self.circuit_breaker and self.circuit_breaker.is_open():
            logger.warning("Circuit breaker is open, skipping cache write")
            return False
        
        try:
            # Serialize response
            data = orjson.dumps(response)
            
            # Compress if needed
            compressed_data, is_compressed = self._compress_data(data)
            
            # Store data
            ttl = ttl or self.ttl_seconds
            await self.client.setex(key, ttl, compressed_data)
            
            # Store metadata
            metadata = {
                "compressed": is_compressed,
                "original_size": len(data),
                "compressed_size": len(compressed_data),
                "timestamp": datetime.utcnow().isoformat(),
                "ttl": ttl,
                "tags": tags or []
            }
            metadata_key = f"{key}:meta"
            await self.client.setex(metadata_key, ttl, orjson.dumps(metadata))
            
            # Update cache size metric
            cache_size.set(len(compressed_data))
            
            # Handle tags for invalidation
            if tags:
                for tag in tags:
                    tag_key = f"tag:{tag}"
                    await self.client.sadd(tag_key, key)
                    await self.client.expire(tag_key, ttl)
            
            logger.info(
                f"Cached response for key: {key[:32]}... "
                f"(size: {len(data)} -> {len(compressed_data)} bytes, "
                f"compressed: {is_compressed})"
            )
            
            if self.circuit_breaker:
                self.circuit_breaker.record_success()
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            self.stats.errors += 1
            cache_errors.inc()
            
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            
            return False
    
    async def invalidate_cache(
        self,
        key: Optional[str] = None,
        pattern: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> int:
        """
        Invalidate cached items.
        
        Args:
            key: Specific key to invalidate
            pattern: Pattern to match keys
            tags: Tags to invalidate
        
        Returns:
            Number of items invalidated
        """
        if not self._connected:
            return 0
        
        try:
            count = 0
            
            # Invalidate specific key
            if key:
                result = await self.client.delete(key, f"{key}:meta")
                count += result // 2  # Count actual items, not metadata
            
            # Invalidate by pattern
            if pattern:
                cursor = 0
                while True:
                    cursor, keys = await self.client.scan(
                        cursor, match=pattern, count=100
                    )
                    if keys:
                        # Delete keys and their metadata
                        all_keys = []
                        for k in keys:
                            all_keys.extend([k, f"{k}:meta"])
                        result = await self.client.delete(*all_keys)
                        count += result // 2
                    if cursor == 0:
                        break
            
            # Invalidate by tags
            if tags:
                for tag in tags:
                    tag_key = f"tag:{tag}"
                    members = await self.client.smembers(tag_key)
                    if members:
                        # Delete tagged keys and their metadata
                        all_keys = []
                        for member in members:
                            all_keys.extend([member, f"{member}:meta"])
                        result = await self.client.delete(*all_keys)
                        count += result // 2
                        # Clean up tag set
                        await self.client.delete(tag_key)
            
            logger.info(f"Invalidated {count} cache entries")
            return count
            
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return 0
    
    async def warm_cache(self, common_queries: List[Dict[str, Any]]) -> int:
        """
        Warm cache with common queries.
        
        Args:
            common_queries: List of common query/response pairs
        
        Returns:
            Number of items warmed
        """
        if not self._connected:
            return 0
        
        count = 0
        for item in common_queries:
            key = item.get("key")
            response = item.get("response")
            ttl = item.get("ttl", self.ttl_seconds)
            
            if key and response:
                success = await self.cache_response(key, response, ttl)
                if success:
                    count += 1
        
        logger.info(f"Warmed cache with {count} items")
        return count
    
    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        # Calculate current stats
        self.stats.calculate_hit_rate()
        
        # Get Redis info if connected
        if self._connected:
            try:
                info = await self.client.info("memory")
                self.stats.cache_size_bytes = info.get("used_memory", 0)
                
                # Get connection count
                pool_stats = self.pool.connection_kwargs if self.pool else {}
                cache_connections.set(len(pool_stats))
                
            except Exception as e:
                logger.error(f"Error getting Redis info: {e}")
        
        return self.stats
    
    async def clear_all(self) -> bool:
        """Clear all cached data."""
        if not self._connected:
            return False
        
        try:
            await self.client.flushdb()
            logger.info("Cleared all cache entries")
            
            # Reset stats
            self.stats = CacheStats()
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Check cache health."""
        health = {
            "connected": self._connected,
            "circuit_breaker_state": None,
            "stats": None,
            "latency_ms": None
        }
        
        if self.circuit_breaker:
            health["circuit_breaker_state"] = self.circuit_breaker.state
        
        if self._connected:
            try:
                start = time.time()
                await self.client.ping()
                health["latency_ms"] = (time.time() - start) * 1000
                health["stats"] = (await self.get_stats()).to_dict()
            except Exception as e:
                health["error"] = str(e)
                health["connected"] = False
        
        return health
"""Semantic cache implementation with Redis backend."""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import numpy as np
import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from ..app.config import settings
from .embeddings import Embedding, EmbeddingGenerator, SimilarityCalculator

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached response."""

    id: str = field(default_factory=lambda: str(uuid4()))
    query: str = ""
    response: str = ""
    embedding: Embedding | None = None

    # Metadata
    model: str = ""
    temperature: float = 0.7
    tenant_id: str | None = None

    # Statistics
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0

    # TTL and versioning
    ttl: int = 3600  # 1 hour default
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "query": self.query,
            "response": self.response,
            "embedding": self.embedding.to_dict() if self.embedding else None,
            "model": self.model,
            "temperature": self.temperature,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "ttl": self.ttl,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        embedding = None
        if data.get("embedding"):
            embedding = Embedding.from_dict(data["embedding"])

        return cls(
            id=data.get("id", str(uuid4())),
            query=data.get("query", ""),
            response=data.get("response", ""),
            embedding=embedding,
            model=data.get("model", ""),
            temperature=data.get("temperature", 0.7),
            tenant_id=data.get("tenant_id"),
            created_at=data.get("created_at", time.time()),
            last_accessed=data.get("last_accessed", time.time()),
            access_count=data.get("access_count", 0),
            ttl=data.get("ttl", 3600),
            version=data.get("version", "1.0"),
        )

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() - self.created_at > self.ttl

    def touch(self):
        """Update last accessed time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache performance statistics."""

    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_entries: int = 0

    # Performance metrics
    avg_similarity_score: float = 0.0
    avg_lookup_time_ms: float = 0.0
    memory_usage_mb: float = 0.0

    # Time-based metrics
    hits_last_hour: int = 0
    queries_last_hour: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_queries == 0:
            return 0.0
        return self.cache_hits / self.total_queries

    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        return 1.0 - self.hit_rate

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_queries": self.total_queries,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": round(self.hit_rate, 3),
            "miss_rate": round(self.miss_rate, 3),
            "total_entries": self.total_entries,
            "avg_similarity_score": round(self.avg_similarity_score, 3),
            "avg_lookup_time_ms": round(self.avg_lookup_time_ms, 2),
            "memory_usage_mb": round(self.memory_usage_mb, 2),
            "hits_last_hour": self.hits_last_hour,
            "queries_last_hour": self.queries_last_hour,
        }


class SemanticCache:
    """Semantic cache with Redis backend and embedding-based similarity."""

    def __init__(
        self,
        redis_url: str = None,
        embedding_generator: EmbeddingGenerator | None = None,
        similarity_calculator: SimilarityCalculator | None = None,
        similarity_threshold: float = 0.85,
        max_entries: int = 10000,
        ttl: int = 3600,
    ):
        self.redis_url = redis_url or settings.redis_url
        self.embedding_generator = embedding_generator or EmbeddingGenerator()
        self.similarity_calculator = similarity_calculator or SimilarityCalculator()
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.default_ttl = ttl

        # Redis connection
        self.redis_client: redis.Redis | None = None
        self.connection_pool: ConnectionPool | None = None

        # Local cache for embeddings (LRU-style)
        self._embedding_cache: dict[str, CacheEntry] = {}
        self._cache_order: list[str] = []

        # Statistics
        self.stats = CacheStats()

        logger.info(f"Semantic cache initialized with threshold {similarity_threshold}")

    async def connect(self):
        """Connect to Redis."""
        if not self.redis_client:
            self.connection_pool = ConnectionPool.from_url(
                self.redis_url, max_connections=settings.redis_max_connections
            )
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)

            # Test connection
            await self.redis_client.ping()
            logger.info("Connected to Redis for semantic caching")

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            await self.connection_pool.disconnect()
            self.redis_client = None
            logger.info("Disconnected from Redis")

    async def get(
        self, query: str, model: str = "", temperature: float = 0.7, tenant_id: str | None = None
    ) -> CacheEntry | None:
        """Get cached response for query using semantic similarity."""
        start_time = time.time()
        self.stats.total_queries += 1

        try:
            # Generate embedding for query
            query_embedding = await self.embedding_generator.generate(query)

            # Get candidate entries from cache
            candidates = await self._get_candidates(tenant_id, model)

            if not candidates:
                self.stats.cache_misses += 1
                return None

            # Find most similar entry
            similar_entries = self.similarity_calculator.find_most_similar(
                query_embedding,
                [c.embedding for c in candidates if c.embedding],
                threshold=self.similarity_threshold,
                top_k=1,
            )

            if not similar_entries:
                self.stats.cache_misses += 1
                return None

            # Get the most similar entry
            best_embedding, similarity_score = similar_entries[0]

            # Find corresponding cache entry
            for candidate in candidates:
                if candidate.embedding and np.array_equal(
                    candidate.embedding.vector, best_embedding.vector
                ):
                    # Check if entry is expired
                    if candidate.is_expired():
                        await self._remove_entry(candidate.id)
                        self.stats.cache_misses += 1
                        return None

                    # Update statistics
                    candidate.touch()
                    self.stats.cache_hits += 1
                    self.stats.avg_similarity_score = (
                        self.stats.avg_similarity_score * 0.9 + similarity_score * 0.1
                    )

                    # Update lookup time
                    lookup_time = (time.time() - start_time) * 1000
                    self.stats.avg_lookup_time_ms = (
                        self.stats.avg_lookup_time_ms * 0.9 + lookup_time * 0.1
                    )

                    logger.debug(f"Cache hit with similarity {similarity_score:.3f}")
                    return candidate

            self.stats.cache_misses += 1
            return None

        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            self.stats.cache_misses += 1
            return None

    async def put(
        self,
        query: str,
        response: str,
        model: str = "",
        temperature: float = 0.7,
        tenant_id: str | None = None,
        ttl: int | None = None,
    ) -> CacheEntry:
        """Put response in cache with semantic embedding."""
        try:
            # Generate embedding for query
            embedding = await self.embedding_generator.generate(query)

            # Create cache entry
            entry = CacheEntry(
                query=query,
                response=response,
                embedding=embedding,
                model=model,
                temperature=temperature,
                tenant_id=tenant_id,
                ttl=ttl or self.default_ttl,
            )

            # Store in Redis
            await self._store_entry(entry)

            # Update local cache
            self._update_local_cache(entry)

            # Update statistics
            self.stats.total_entries += 1

            logger.debug(f"Cached response for query: {query[:50]}...")
            return entry

        except Exception as e:
            logger.error(f"Error putting in cache: {e}")
            raise

    async def _get_candidates(self, tenant_id: str | None, model: str) -> list[CacheEntry]:
        """Get candidate cache entries for similarity matching."""
        candidates = []

        # First check local cache
        for entry in self._embedding_cache.values():
            # Filter by tenant and model
            if tenant_id and entry.tenant_id != tenant_id:
                continue
            if model and entry.model != model:
                continue

            candidates.append(entry)

        # If not enough candidates, fetch from Redis
        if len(candidates) < 100 and self.redis_client:
            try:
                # Get keys matching pattern
                pattern = f"cache:{tenant_id or '*'}:{model or '*'}:*"
                keys = await self.redis_client.keys(pattern)

                # Fetch entries
                for key in keys[:100]:  # Limit to 100 entries
                    data = await self.redis_client.get(key)
                    if data:
                        entry_dict = json.loads(data)
                        entry = CacheEntry.from_dict(entry_dict)

                        # Skip if already in candidates
                        if entry.id not in [c.id for c in candidates]:
                            candidates.append(entry)
                            # Update local cache
                            self._update_local_cache(entry)

            except Exception as e:
                logger.error(f"Error fetching from Redis: {e}")

        return candidates

    async def _store_entry(self, entry: CacheEntry):
        """Store cache entry in Redis."""
        if not self.redis_client:
            return

        try:
            # Create Redis key
            key = f"cache:{entry.tenant_id or 'global'}:{entry.model}:{entry.id}"

            # Serialize entry
            data = json.dumps(entry.to_dict())

            # Store with TTL
            await self.redis_client.setex(key, entry.ttl, data)

        except Exception as e:
            logger.error(f"Error storing in Redis: {e}")

    async def _remove_entry(self, entry_id: str):
        """Remove cache entry."""
        # Remove from local cache
        if entry_id in self._embedding_cache:
            del self._embedding_cache[entry_id]
            if entry_id in self._cache_order:
                self._cache_order.remove(entry_id)

        # Remove from Redis
        if self.redis_client:
            try:
                pattern = f"cache:*:*:{entry_id}"
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
            except Exception as e:
                logger.error(f"Error removing from Redis: {e}")

    def _update_local_cache(self, entry: CacheEntry):
        """Update local LRU cache."""
        # Add to cache
        self._embedding_cache[entry.id] = entry

        # Update order (LRU)
        if entry.id in self._cache_order:
            self._cache_order.remove(entry.id)
        self._cache_order.append(entry.id)

        # Evict if over limit
        while len(self._embedding_cache) > self.max_entries:
            oldest_id = self._cache_order.pop(0)
            del self._embedding_cache[oldest_id]

    async def clear(self, tenant_id: str | None = None):
        """Clear cache entries."""
        # Clear local cache
        if tenant_id:
            # Clear only tenant entries
            to_remove = [
                entry_id
                for entry_id, entry in self._embedding_cache.items()
                if entry.tenant_id == tenant_id
            ]
            for entry_id in to_remove:
                del self._embedding_cache[entry_id]
                if entry_id in self._cache_order:
                    self._cache_order.remove(entry_id)
        else:
            # Clear all
            self._embedding_cache.clear()
            self._cache_order.clear()

        # Clear Redis
        if self.redis_client:
            try:
                pattern = f"cache:{tenant_id or '*'}:*"
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
            except Exception as e:
                logger.error(f"Error clearing Redis: {e}")

        logger.info(f"Cache cleared for tenant: {tenant_id or 'all'}")

    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        # Update entry count
        self.stats.total_entries = len(self._embedding_cache)

        # Estimate memory usage
        total_size = 0
        for entry in self._embedding_cache.values():
            # Rough estimate
            total_size += len(json.dumps(entry.to_dict()))
        self.stats.memory_usage_mb = total_size / (1024 * 1024)

        return self.stats

    async def warmup(self, queries: list[str], responses: list[str], **kwargs):
        """Warmup cache with predefined queries and responses."""
        logger.info(f"Warming up cache with {len(queries)} entries")

        for query, response in zip(queries, responses, strict=False):
            await self.put(query, response, **kwargs)

        logger.info("Cache warmup complete")

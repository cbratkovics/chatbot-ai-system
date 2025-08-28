"""Semantic cache implementation using embeddings for similarity matching."""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

import numpy as np
from redis import asyncio as aioredis
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class SemanticCache:
    """Semantic cache using embeddings for intelligent response caching."""

    def __init__(self, redis_client: aioredis.Redis, config: dict[str, Any] | None = None):
        """Initialize semantic cache.

        Args:
            redis_client: Redis client for cache storage
            config: Cache configuration
        """
        self.redis_client = redis_client
        config = config or {}

        self.similarity_threshold = config.get("similarity_threshold", 0.85)
        self.ttl_seconds = config.get("ttl_seconds", 3600)
        self.max_size_mb = config.get("max_size_mb", 100)
        self.embedding_dimension = config.get("embedding_dimension", 1536)
        self.cache_prefix = "semantic_cache:"

    async def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI()

            response = await client.embeddings.create(model="text-embedding-ada-002", input=text)
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return np.random.rand(self.embedding_dimension).tolist()

    def _calculate_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score
        """
        if len(vec1) != len(vec2):
            return 0.0

        vec1 = np.array(vec1).reshape(1, -1)
        vec2 = np.array(vec2).reshape(1, -1)

        similarity = cosine_similarity(vec1, vec2)[0][0]
        return float(similarity)

    async def get(self, query: str) -> dict[str, Any] | None:
        """Get cached response for query.

        Args:
            query: Query text

        Returns:
            Cached response if found
        """
        try:
            query_embedding = await self._generate_embedding(query)

            cache_keys = await self.redis_client.keys(f"{self.cache_prefix}*")

            best_match = None
            best_similarity = 0.0

            for key in cache_keys:
                cached_data = await self.redis_client.get(key)
                if not cached_data:
                    continue

                try:
                    data = json.loads(cached_data)
                    cached_embedding = data.get("embedding", [])

                    similarity = self._calculate_similarity(query_embedding, cached_embedding)

                    if similarity > best_similarity and similarity >= self.similarity_threshold:
                        best_similarity = similarity
                        best_match = data.get("response")
                        best_match["cached"] = True
                        best_match["cache_similarity"] = similarity

                except json.JSONDecodeError:
                    continue

            if best_match:
                logger.info(f"Cache hit with similarity {best_similarity:.3f}")
                return best_match

            logger.info("Cache miss")
            return None

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(self, query: str, response: dict[str, Any], ttl: int | None = None) -> bool:
        """Set cache entry.

        Args:
            query: Query text
            response: Response to cache
            ttl: Time to live in seconds

        Returns:
            Success status
        """
        try:
            response_size = len(json.dumps(response))
            if response_size > self.max_size_mb * 1024 * 1024:
                raise ValueError(f"Response size {response_size} exceeds maximum cache size")

            query_embedding = await self._generate_embedding(query)

            cache_data = {
                "query": query,
                "embedding": query_embedding,
                "response": response,
                "timestamp": datetime.utcnow().isoformat(),
                "size_bytes": response_size,
            }

            cache_key = f"{self.cache_prefix}{hashlib.md5(query.encode()).hexdigest()}"

            ttl = ttl or self.ttl_seconds
            await self.redis_client.setex(cache_key, ttl, json.dumps(cache_data))

            logger.info(f"Cached response for query hash {cache_key}")
            return True

        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def invalidate(self, pattern: str | None = None) -> int:
        """Invalidate cache entries.

        Args:
            pattern: Pattern to match keys

        Returns:
            Number of invalidated entries
        """
        try:
            if pattern:
                keys = await self.redis_client.keys(f"{self.cache_prefix}{pattern}")
            else:
                keys = await self.redis_client.keys(f"{self.cache_prefix}*")

            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {deleted} cache entries")
                return deleted

            return 0

        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return 0

    async def get_ttl(self, key: str) -> int:
        """Get TTL for cache key.

        Args:
            key: Cache key

        Returns:
            TTL in seconds
        """
        try:
            ttl = await self.redis_client.ttl(f"{self.cache_prefix}{key}")
            return ttl
        except Exception as e:
            logger.error(f"Failed to get TTL: {e}")
            return -1

    async def set_batch(
        self, items: list[tuple[str, dict[str, Any]]], ttl: int | None = None
    ) -> int:
        """Set multiple cache entries.

        Args:
            items: List of (query, response) tuples
            ttl: Time to live in seconds

        Returns:
            Number of successfully cached items
        """
        success_count = 0

        for query, response in items:
            if await self.set(query, response, ttl):
                success_count += 1

        return success_count

    async def warmup(self, data: list[dict[str, Any]]) -> int:
        """Warmup cache with predefined data.

        Args:
            data: List of cache entries

        Returns:
            Number of warmed entries
        """
        warmed = 0

        for entry in data:
            query = entry.get("query")
            response = entry.get("response")

            if query and response:
                if await self.set(query, response):
                    warmed += 1

        logger.info(f"Warmed {warmed} cache entries")
        return warmed

    async def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        try:
            keys = await self.redis_client.keys(f"{self.cache_prefix}*")

            total_size = 0
            oldest_entry = None
            newest_entry = None

            for key in keys:
                data = await self.redis_client.get(key)
                if data:
                    total_size += len(data)
                    try:
                        entry = json.loads(data)
                        timestamp = datetime.fromisoformat(entry["timestamp"])

                        if not oldest_entry or timestamp < oldest_entry:
                            oldest_entry = timestamp
                        if not newest_entry or timestamp > newest_entry:
                            newest_entry = timestamp
                    except (json.JSONDecodeError, KeyError):
                        continue

            return {
                "total_entries": len(keys),
                "total_size_mb": total_size / (1024 * 1024),
                "oldest_entry": oldest_entry.isoformat() if oldest_entry else None,
                "newest_entry": newest_entry.isoformat() if newest_entry else None,
                "similarity_threshold": self.similarity_threshold,
                "ttl_seconds": self.ttl_seconds,
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

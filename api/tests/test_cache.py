from unittest.mock import Mock, patch

import numpy as np
import pytest


@pytest.mark.asyncio
async def test_semantic_cache_similarity():
    with patch("app.services.cache.semantic_cache.SentenceTransformer") as mock_transformer:
        # Mock the sentence transformer
        mock_model = Mock()
        mock_model.encode.return_value = np.array([[1.0, 0.0, 0.0]])
        mock_transformer.return_value = mock_model

        from api.services.cache.semantic_cache import SemanticCache

        cache = SemanticCache(similarity_threshold=0.8)

        # Test cosine similarity calculation
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        similarity = cache._cosine_similarity(vec1, vec2)
        assert similarity == 1.0

        # Test orthogonal vectors
        vec3 = [0.0, 1.0, 0.0]
        similarity = cache._cosine_similarity(vec1, vec3)
        assert similarity == 0.0


@pytest.mark.asyncio
async def test_cache_operations():
    with patch("app.services.cache.semantic_cache.SentenceTransformer") as mock_transformer, patch(
        "app.services.cache.semantic_cache.redis.asyncio.from_url"
    ) as mock_redis:
        # Mock the sentence transformer
        mock_model = Mock()
        mock_model.encode.return_value = np.array([[1.0, 0.0, 0.0]])
        mock_transformer.return_value = mock_model

        # Mock Redis
        mock_redis_client = Mock()
        mock_redis_client.get = Mock(return_value=None)
        mock_redis_client.set = Mock(return_value=True)
        mock_redis.return_value = mock_redis_client

        from api.services.cache.semantic_cache import SemanticCache

        cache = SemanticCache()

        # Test cache miss
        result = await cache.get_cached_response("test query")
        assert result is None

        # Test cache storage
        await cache.cache_response("test query", "test response")

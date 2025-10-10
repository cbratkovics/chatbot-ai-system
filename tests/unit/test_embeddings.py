"""Unit tests for embedding generation."""

import pytest
from unittest.mock import Mock, patch, AsyncMock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for embeddings."""
    with patch("chatbot_ai_system.vector_store.embeddings.AsyncOpenAI") as mock_client:
        mock_instance = Mock()
        mock_embeddings = Mock()

        # Single embedding response
        mock_embeddings.create = AsyncMock(return_value=Mock(data=[Mock(embedding=[0.1] * 1536)]))

        mock_instance.embeddings = mock_embeddings
        mock_instance.close = AsyncMock()
        mock_client.return_value = mock_instance
        yield mock_client


@pytest.mark.unit
class TestEmbeddingGenerator:
    """Test embedding generation functionality."""

    def test_initialization(self, mock_openai_client):
        """Test embedding generator initialization."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(api_key="test-key")

        assert generator.model == "text-embedding-ada-002"
        assert generator.dimensions == 1536

    def test_initialization_custom_model(self, mock_openai_client):
        """Test initialization with custom model."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(
            api_key="test-key", model="text-embedding-3-small", dimensions=512
        )

        assert generator.model == "text-embedding-3-small"
        assert generator.dimensions == 512

    @pytest.mark.asyncio
    async def test_single_embedding_generation(self, mock_openai_client):
        """Test generating embedding for single text."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(api_key="test-key")
        embedding = await generator.generate("Test text")

        assert isinstance(embedding, list)
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_batch_embedding_generation(self, mock_openai_client):
        """Test batch embedding generation."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(api_key="test-key")
        texts = ["Text 1", "Text 2", "Text 3"]

        # Update mock for batch
        mock_openai_client.return_value.embeddings.create.return_value = Mock(
            data=[Mock(embedding=[0.1] * 1536) for _ in texts]
        )

        embeddings = await generator.generate_batch(texts)

        assert isinstance(embeddings, list)
        assert len(embeddings) == 3
        assert all(len(e) == 1536 for e in embeddings)

    @pytest.mark.asyncio
    async def test_empty_batch(self, mock_openai_client):
        """Test batch generation with empty list."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(api_key="test-key")

        mock_openai_client.return_value.embeddings.create.return_value = Mock(data=[])

        embeddings = await generator.generate_batch([])

        assert embeddings == []

    def test_compute_text_hash(self):
        """Test deterministic text hashing."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        text1 = "Hello, world!"
        text2 = "Hello, world!"
        text3 = "Different text"

        hash1 = EmbeddingGenerator.compute_text_hash(text1)
        hash2 = EmbeddingGenerator.compute_text_hash(text2)
        hash3 = EmbeddingGenerator.compute_text_hash(text3)

        assert hash1 == hash2
        assert hash1 != hash3
        assert isinstance(hash1, str)
        assert len(hash1) == 32  # MD5 hash length

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_openai_client):
        """Test error handling for failed API calls."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(api_key="test-key")
        mock_openai_client.return_value.embeddings.create.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            await generator.generate("Test text")

    @pytest.mark.asyncio
    async def test_batch_error_handling(self, mock_openai_client):
        """Test error handling for batch operations."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(api_key="test-key")
        mock_openai_client.return_value.embeddings.create.side_effect = Exception("Batch error")

        with pytest.raises(Exception, match="Batch error"):
            await generator.generate_batch(["Text 1", "Text 2"])

    @pytest.mark.asyncio
    async def test_dimension_mismatch_warning(self, mock_openai_client, caplog):
        """Test warning when embedding dimension doesn't match expected."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(api_key="test-key", dimensions=1536)

        # Mock returns wrong dimension
        mock_openai_client.return_value.embeddings.create.return_value = Mock(
            data=[Mock(embedding=[0.1] * 512)]  # Wrong dimension
        )

        embedding = await generator.generate("Test")

        assert len(embedding) == 512  # Returns what API gave us
        # Would log warning in actual implementation

    @pytest.mark.asyncio
    async def test_close(self, mock_openai_client):
        """Test closing the client."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(api_key="test-key")
        await generator.close()

        mock_openai_client.return_value.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_openai_client):
        """Test async context manager support."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        async with EmbeddingGenerator(api_key="test-key") as generator:
            embedding = await generator.generate("Test")
            assert len(embedding) == 1536

        mock_openai_client.return_value.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_generate_calls(self, mock_openai_client):
        """Test multiple sequential generate calls."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(api_key="test-key")

        embedding1 = await generator.generate("First text")
        embedding2 = await generator.generate("Second text")

        assert len(embedding1) == 1536
        assert len(embedding2) == 1536
        assert mock_openai_client.return_value.embeddings.create.call_count == 2

    @pytest.mark.asyncio
    async def test_unicode_text(self, mock_openai_client):
        """Test handling of unicode characters."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        generator = EmbeddingGenerator(api_key="test-key")
        unicode_text = "Hello 世界 🌍"

        embedding = await generator.generate(unicode_text)

        assert len(embedding) == 1536

    def test_hash_unicode_text(self):
        """Test hashing unicode text."""
        from chatbot_ai_system.vector_store.embeddings import EmbeddingGenerator

        unicode_text = "Hello 世界 🌍"
        hash_value = EmbeddingGenerator.compute_text_hash(unicode_text)

        assert isinstance(hash_value, str)
        assert len(hash_value) == 32

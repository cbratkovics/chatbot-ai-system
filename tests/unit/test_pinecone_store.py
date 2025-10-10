"""Unit tests for Pinecone vector store."""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import time


@pytest.fixture
def mock_pinecone_index():
    """Mock Pinecone index."""
    mock = Mock()
    mock.upsert = Mock(return_value=Mock(upserted_count=5))
    mock.query = Mock(
        return_value=Mock(
            matches=[
                Mock(id="doc1", score=0.95, metadata={"text": "Test document 1"}),
                Mock(id="doc2", score=0.87, metadata={"text": "Test document 2"}),
            ]
        )
    )
    mock.delete = Mock(return_value={})
    mock.describe_index_stats = Mock(
        return_value=Mock(total_vector_count=100, dimension=1536, index_fullness=0.5, namespaces={})
    )
    return mock


@pytest.fixture
def mock_pinecone_client(mock_pinecone_index):
    """Mock Pinecone client."""
    with patch("chatbot_ai_system.vector_store.pinecone_store.Pinecone") as mock_pc:
        mock_instance = Mock()
        mock_instance.Index.return_value = mock_pinecone_index
        mock_instance.list_indexes.return_value = []
        mock_instance.create_index = Mock()
        mock_instance.describe_index = Mock(return_value=Mock(status=Mock(ready=True)))
        mock_pc.return_value = mock_instance
        yield mock_pc


@pytest.fixture
def mock_embedding_generator():
    """Mock embedding generator."""
    mock_gen = Mock()
    mock_gen.generate = AsyncMock(return_value=[0.1] * 1536)
    mock_gen.generate_batch = AsyncMock(return_value=[[0.1] * 1536 for _ in range(5)])
    return mock_gen


@pytest.mark.unit
class TestPineconeVectorStore:
    """Test Pinecone vector store functionality."""

    def test_initialization(self, mock_pinecone_client):
        """Test vector store initialization."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key", index_name="test-index", environment="us-east-1"
        )

        assert store.index_name == "test-index"
        assert store.dimension == 1536
        assert store.metric == "cosine"
        assert store.environment == "us-east-1"

    def test_initialization_creates_index(self, mock_pinecone_client):
        """Test that initialization creates index if not exists."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        mock_pinecone_client.return_value.list_indexes.return_value = []

        store = PineconeVectorStore(
            api_key="test-key", index_name="new-index", environment="us-east-1"
        )

        mock_pinecone_client.return_value.create_index.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_documents(self, mock_pinecone_client, mock_embedding_generator):
        """Test document upsert with embeddings."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="us-east-1",
            embedding_generator=mock_embedding_generator,
        )

        documents = [
            {"id": "doc1", "text": "Test document 1", "metadata": {"source": "test"}},
            {"id": "doc2", "text": "Test document 2", "metadata": {"source": "test"}},
        ]

        result = await store.upsert(documents)

        assert result is not None
        assert "upserted_count" in result
        assert result["upserted_count"] == 5
        mock_embedding_generator.generate_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_without_embedding_generator_raises_error(self, mock_pinecone_client):
        """Test that upsert without embedding generator raises error."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key", index_name="test-index", environment="us-east-1"
        )

        documents = [{"id": "doc1", "text": "Test", "metadata": {}}]

        with pytest.raises(ValueError, match="EmbeddingGenerator not configured"):
            await store.upsert(documents)

    @pytest.mark.asyncio
    async def test_query_vector_store(self, mock_pinecone_client, mock_embedding_generator):
        """Test semantic search query."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="us-east-1",
            embedding_generator=mock_embedding_generator,
        )

        results = await store.query(
            query_text="What is Python?", top_k=5, filter={"source": "documentation"}
        )

        assert isinstance(results, list)
        assert len(results) == 2
        assert "score" in results[0]
        assert "id" in results[0]
        assert results[0]["score"] == 0.95
        mock_embedding_generator.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_with_metadata(self, mock_pinecone_client, mock_embedding_generator):
        """Test query includes metadata when requested."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="us-east-1",
            embedding_generator=mock_embedding_generator,
        )

        results = await store.query(query_text="test query", top_k=5, include_metadata=True)

        assert len(results) > 0
        assert "metadata" in results[0]

    @pytest.mark.asyncio
    async def test_delete_by_ids(self, mock_pinecone_client):
        """Test vector deletion by IDs."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key", index_name="test-index", environment="us-east-1"
        )

        result = await store.delete(ids=["doc1", "doc2"])

        assert "deleted_count" in result
        assert result["deleted_count"] == 2
        store.index.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_all(self, mock_pinecone_client):
        """Test delete all vectors in namespace."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key", index_name="test-index", environment="us-east-1"
        )

        result = await store.delete(delete_all=True, namespace="test-namespace")

        assert result["deleted"] == "all"
        assert result["namespace"] == "test-namespace"

    @pytest.mark.asyncio
    async def test_delete_without_params_raises_error(self, mock_pinecone_client):
        """Test delete without parameters raises error."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key", index_name="test-index", environment="us-east-1"
        )

        with pytest.raises(ValueError, match="Must specify"):
            await store.delete()

    def test_get_stats(self, mock_pinecone_client):
        """Test getting index statistics."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key", index_name="test-index", environment="us-east-1"
        )

        stats = store.get_stats()

        assert "total_vector_count" in stats
        assert "dimension" in stats
        assert stats["total_vector_count"] == 100

    def test_context_manager(self, mock_pinecone_client):
        """Test context manager support."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        with PineconeVectorStore(
            api_key="test-key", index_name="test-index", environment="us-east-1"
        ) as store:
            assert store.index_name == "test-index"

    @pytest.mark.asyncio
    async def test_batch_upsert(self, mock_pinecone_client, mock_embedding_generator):
        """Test batch upsert with custom batch size."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="us-east-1",
            embedding_generator=mock_embedding_generator,
        )

        documents = [{"id": f"doc{i}", "text": f"Document {i}", "metadata": {}} for i in range(10)]

        result = await store.upsert(documents, batch_size=5)

        assert result["batch_count"] >= 1  # 10 documents / 5 batch size = 2 batches minimum

    @pytest.mark.asyncio
    async def test_namespace_support(self, mock_pinecone_client, mock_embedding_generator):
        """Test multi-tenant namespace support."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="us-east-1",
            embedding_generator=mock_embedding_generator,
        )

        documents = [{"id": "doc1", "text": "Test", "metadata": {}}]
        result = await store.upsert(documents, namespace="tenant-123")

        assert result["namespace"] == "tenant-123"

    @pytest.mark.asyncio
    async def test_error_handling_upsert(self, mock_pinecone_client, mock_embedding_generator):
        """Test error handling for failed upsert operations."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="us-east-1",
            embedding_generator=mock_embedding_generator,
        )

        store.index.upsert.side_effect = Exception("Pinecone API error")

        with pytest.raises(Exception, match="Pinecone API error"):
            await store.upsert([{"id": "doc1", "text": "Test", "metadata": {}}])

    @pytest.mark.asyncio
    async def test_error_handling_query(self, mock_pinecone_client, mock_embedding_generator):
        """Test error handling for failed query operations."""
        from chatbot_ai_system.vector_store.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="us-east-1",
            embedding_generator=mock_embedding_generator,
        )

        mock_embedding_generator.generate.side_effect = Exception("Embedding error")

        with pytest.raises(Exception, match="Embedding error"):
            await store.query("test query")

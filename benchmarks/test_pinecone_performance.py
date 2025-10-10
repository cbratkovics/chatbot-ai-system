"""Performance benchmarks for Pinecone vector store operations.

This module tests and measures the performance of:
- Embedding generation
- Vector upsert operations (single and batch)
- Vector search queries
- Index statistics retrieval
- Namespace operations
"""

import time
import pytest
import asyncio
from typing import List, Dict, Any
from unittest.mock import Mock, patch, AsyncMock


@pytest.fixture
def mock_pinecone_index():
    """Mock Pinecone index for benchmarking."""
    mock = Mock()
    mock.upsert = Mock(return_value=Mock(upserted_count=100))
    mock.query = Mock(
        return_value=Mock(
            matches=[
                Mock(id=f"doc{i}", score=0.95 - i * 0.05, metadata={"text": f"Document {i}"})
                for i in range(10)
            ]
        )
    )
    mock.delete = Mock(return_value={})
    mock.describe_index_stats = Mock(
        return_value=Mock(
            total_vector_count=10000,
            dimension=1536,
            index_fullness=0.5,
            namespaces={}
        )
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
    mock_gen.generate_batch = AsyncMock(return_value=[[0.1] * 1536 for _ in range(100)])
    return mock_gen


class TestEmbeddingPerformance:
    """Benchmark embedding generation performance."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_single_embedding_generation_speed(self, mock_embedding_generator):
        """Benchmark single text embedding generation."""
        from chatbot_ai_system.vector_store import EmbeddingGenerator

        # Simulate realistic embedding generation time
        async def realistic_generate(text: str):
            await asyncio.sleep(0.05)  # Simulate API latency
            return [0.1] * 1536

        mock_embedding_generator.generate = AsyncMock(side_effect=realistic_generate)

        with patch("chatbot_ai_system.vector_store.embeddings.AsyncOpenAI"):
            generator = EmbeddingGenerator(api_key="test-key")
            generator.client.embeddings.create = AsyncMock(
                return_value=Mock(data=[Mock(embedding=[0.1] * 1536)])
            )

            start = time.time()
            embedding = await generator.generate("Test document for embedding")
            duration = time.time() - start

            assert len(embedding) == 1536
            print(f"\nSingle embedding generation: {duration*1000:.2f}ms")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_batch_embedding_generation_speed(self, mock_embedding_generator):
        """Benchmark batch embedding generation."""
        from chatbot_ai_system.vector_store import EmbeddingGenerator

        batch_size = 100
        texts = [f"Document {i} for batch embedding" for i in range(batch_size)]

        # Simulate realistic batch generation time
        async def realistic_batch_generate(texts: List[str]):
            await asyncio.sleep(0.2)  # Simulate API latency for batch
            return [[0.1] * 1536 for _ in texts]

        mock_embedding_generator.generate_batch = AsyncMock(side_effect=realistic_batch_generate)

        with patch("chatbot_ai_system.vector_store.embeddings.AsyncOpenAI"):
            generator = EmbeddingGenerator(api_key="test-key")
            generator.client.embeddings.create = AsyncMock(
                return_value=Mock(
                    data=[Mock(embedding=[0.1] * 1536) for _ in range(batch_size)]
                )
            )

            start = time.time()
            embeddings = await generator.generate_batch(texts)
            duration = time.time() - start

            assert len(embeddings) == batch_size
            throughput = batch_size / duration
            print(f"\nBatch embedding ({batch_size} docs): {duration*1000:.2f}ms")
            print(f"Throughput: {throughput:.2f} embeddings/sec")


class TestVectorUpsertPerformance:
    """Benchmark vector upsert operations."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_single_document_upsert_speed(
        self, mock_pinecone_client, mock_embedding_generator
    ):
        """Benchmark single document upsert."""
        from chatbot_ai_system.vector_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="test",
            embedding_generator=mock_embedding_generator,
        )

        documents = [
            {
                "id": "doc1",
                "text": "Single document for upsert benchmark",
                "metadata": {"category": "test"},
            }
        ]

        start = time.time()
        result = await store.upsert(documents)
        duration = time.time() - start

        assert result["upserted_count"] > 0
        print(f"\nSingle document upsert: {duration*1000:.2f}ms")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_batch_upsert_performance(
        self, mock_pinecone_client, mock_embedding_generator
    ):
        """Benchmark batch document upsert."""
        from chatbot_ai_system.vector_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="test",
            embedding_generator=mock_embedding_generator,
        )

        # Test different batch sizes
        batch_sizes = [10, 50, 100]

        for batch_size in batch_sizes:
            documents = [
                {
                    "id": f"doc{i}",
                    "text": f"Document {i} for batch upsert",
                    "metadata": {"index": i, "batch_size": batch_size},
                }
                for i in range(batch_size)
            ]

            start = time.time()
            result = await store.upsert(documents, batch_size=50)
            duration = time.time() - start

            throughput = batch_size / duration
            print(f"\nBatch upsert ({batch_size} docs): {duration*1000:.2f}ms")
            print(f"Throughput: {throughput:.2f} docs/sec")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_large_batch_upsert_performance(
        self, mock_pinecone_client, mock_embedding_generator
    ):
        """Benchmark large batch upsert (1000 documents)."""
        from chatbot_ai_system.vector_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="test",
            embedding_generator=mock_embedding_generator,
        )

        batch_size = 1000
        documents = [
            {
                "id": f"doc{i}",
                "text": f"Document {i} content for large batch test",
                "metadata": {"index": i},
            }
            for i in range(batch_size)
        ]

        start = time.time()
        result = await store.upsert(documents, batch_size=100)
        duration = time.time() - start

        throughput = batch_size / duration
        print(f"\nLarge batch upsert ({batch_size} docs): {duration:.2f}s")
        print(f"Throughput: {throughput:.2f} docs/sec")
        print(f"Batch count: {result['batch_count']}")


class TestVectorQueryPerformance:
    """Benchmark vector search query operations."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_single_query_speed(
        self, mock_pinecone_client, mock_embedding_generator
    ):
        """Benchmark single vector search query."""
        from chatbot_ai_system.vector_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="test",
            embedding_generator=mock_embedding_generator,
        )

        start = time.time()
        results = await store.query(
            query_text="What is machine learning?",
            top_k=10,
            include_metadata=True,
        )
        duration = time.time() - start

        assert len(results) > 0
        print(f"\nSingle query (top_k=10): {duration*1000:.2f}ms")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_query_with_different_top_k(
        self, mock_pinecone_client, mock_embedding_generator
    ):
        """Benchmark queries with different top_k values."""
        from chatbot_ai_system.vector_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="test",
            embedding_generator=mock_embedding_generator,
        )

        top_k_values = [5, 10, 20, 50]

        for top_k in top_k_values:
            # Update mock to return correct number of results
            mock_pinecone_client.return_value.Index.return_value.query.return_value = Mock(
                matches=[
                    Mock(id=f"doc{i}", score=0.95 - i * 0.01, metadata={"text": f"Doc {i}"})
                    for i in range(min(top_k, 50))
                ]
            )

            start = time.time()
            results = await store.query(
                query_text="Test query for different top_k",
                top_k=top_k,
                include_metadata=True,
            )
            duration = time.time() - start

            print(f"\nQuery with top_k={top_k}: {duration*1000:.2f}ms")
            print(f"Results returned: {len(results)}")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_query_with_filters(
        self, mock_pinecone_client, mock_embedding_generator
    ):
        """Benchmark queries with metadata filters."""
        from chatbot_ai_system.vector_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="test",
            embedding_generator=mock_embedding_generator,
        )

        filters = [
            {"category": "tech"},
            {"category": "tech", "year": 2024},
            {"category": {"$in": ["tech", "science"]}, "rating": {"$gte": 4.0}},
        ]

        for filter_dict in filters:
            start = time.time()
            results = await store.query(
                query_text="Filtered query test",
                top_k=10,
                filter=filter_dict,
                include_metadata=True,
            )
            duration = time.time() - start

            print(f"\nQuery with filter {filter_dict}: {duration*1000:.2f}ms")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_concurrent_queries(
        self, mock_pinecone_client, mock_embedding_generator
    ):
        """Benchmark concurrent query performance."""
        from chatbot_ai_system.vector_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="test",
            embedding_generator=mock_embedding_generator,
        )

        num_concurrent = 10
        queries = [f"Concurrent query {i}" for i in range(num_concurrent)]

        start = time.time()
        tasks = [
            store.query(query_text=query, top_k=5, include_metadata=True)
            for query in queries
        ]
        results = await asyncio.gather(*tasks)
        duration = time.time() - start

        throughput = num_concurrent / duration
        print(f"\n{num_concurrent} concurrent queries: {duration*1000:.2f}ms")
        print(f"Throughput: {throughput:.2f} queries/sec")
        print(f"Average per query: {duration/num_concurrent*1000:.2f}ms")


class TestVectorDeletePerformance:
    """Benchmark vector deletion operations."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_delete_by_ids_speed(self, mock_pinecone_client):
        """Benchmark deletion by IDs."""
        from chatbot_ai_system.vector_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="test",
        )

        ids_to_delete = [f"doc{i}" for i in range(100)]

        start = time.time()
        result = await store.delete(ids=ids_to_delete)
        duration = time.time() - start

        print(f"\nDelete 100 vectors by ID: {duration*1000:.2f}ms")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_delete_by_filter_speed(self, mock_pinecone_client):
        """Benchmark deletion by metadata filter."""
        from chatbot_ai_system.vector_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="test",
        )

        start = time.time()
        result = await store.delete(filter={"category": "test"}, namespace="benchmark")
        duration = time.time() - start

        print(f"\nDelete by filter: {duration*1000:.2f}ms")


class TestIndexStatistics:
    """Benchmark index statistics operations."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_get_stats_speed(self, mock_pinecone_client):
        """Benchmark index statistics retrieval."""
        from chatbot_ai_system.vector_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="test",
        )

        start = time.time()
        stats = store.get_stats()
        duration = time.time() - start

        assert "total_vector_count" in stats
        print(f"\nGet index statistics: {duration*1000:.2f}ms")

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_get_namespace_stats_speed(self, mock_pinecone_client):
        """Benchmark namespace statistics retrieval."""
        from chatbot_ai_system.vector_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="test",
        )

        start = time.time()
        stats = store.get_stats(namespace="benchmark")
        duration = time.time() - start

        print(f"\nGet namespace statistics: {duration*1000:.2f}ms")


class TestEndToEndPerformance:
    """End-to-end performance tests."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_complete_workflow_performance(
        self, mock_pinecone_client, mock_embedding_generator
    ):
        """Benchmark complete workflow: upsert, query, delete."""
        from chatbot_ai_system.vector_store import PineconeVectorStore

        store = PineconeVectorStore(
            api_key="test-key",
            index_name="test-index",
            environment="test",
            embedding_generator=mock_embedding_generator,
        )

        # Phase 1: Upsert documents
        documents = [
            {
                "id": f"workflow_doc{i}",
                "text": f"Document {i} for workflow test",
                "metadata": {"index": i},
            }
            for i in range(50)
        ]

        start_upsert = time.time()
        upsert_result = await store.upsert(documents, batch_size=25)
        upsert_duration = time.time() - start_upsert

        # Phase 2: Query documents
        start_query = time.time()
        query_results = await store.query(
            query_text="Workflow test query",
            top_k=10,
            include_metadata=True,
        )
        query_duration = time.time() - start_query

        # Phase 3: Get statistics
        start_stats = time.time()
        stats = store.get_stats()
        stats_duration = time.time() - start_stats

        # Phase 4: Delete documents
        ids_to_delete = [f"workflow_doc{i}" for i in range(50)]
        start_delete = time.time()
        delete_result = await store.delete(ids=ids_to_delete)
        delete_duration = time.time() - start_delete

        total_duration = upsert_duration + query_duration + stats_duration + delete_duration

        print("\n=== End-to-End Workflow Performance ===")
        print(f"Upsert 50 documents: {upsert_duration*1000:.2f}ms")
        print(f"Query (top_k=10): {query_duration*1000:.2f}ms")
        print(f"Get statistics: {stats_duration*1000:.2f}ms")
        print(f"Delete 50 documents: {delete_duration*1000:.2f}ms")
        print(f"Total workflow time: {total_duration*1000:.2f}ms")


# Performance reporting utility
def print_performance_summary():
    """Print overall performance summary."""
    print("\n" + "=" * 60)
    print("PINECONE PERFORMANCE BENCHMARK SUMMARY")
    print("=" * 60)
    print("\nNote: These are mock-based benchmarks.")
    print("Real-world performance depends on:")
    print("  - Network latency to Pinecone servers")
    print("  - OpenAI API response times")
    print("  - Document size and complexity")
    print("  - Pinecone index size and configuration")
    print("  - Concurrent request load")
    print("\nFor production benchmarks, run against live services.")
    print("=" * 60)


if __name__ == "__main__":
    print_performance_summary()

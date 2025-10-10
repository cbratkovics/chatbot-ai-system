"""Pinecone vector store implementation for semantic search."""

from typing import List, Dict, Any, Optional
import logging
import time

from pinecone import Pinecone, ServerlessSpec

from .embeddings import EmbeddingGenerator

logger = logging.getLogger(__name__)


class PineconeVectorStore:
    """
    Production-ready Pinecone vector store for semantic search and retrieval.

    Features:
    - Automatic index creation and management
    - Batch upsert operations
    - Filtered queries with metadata
    - Namespace support for multi-tenancy
    - Error handling and retry logic
    """

    def __init__(
        self,
        api_key: str,
        index_name: str,
        environment: str = "us-east-1",
        dimension: int = 1536,
        metric: str = "cosine",
        embedding_generator: Optional[EmbeddingGenerator] = None,
    ):
        """
        Initialize Pinecone vector store.

        Args:
            api_key: Pinecone API key
            index_name: Name of the Pinecone index
            environment: Pinecone environment/region
            dimension: Vector dimension (must match embedding model)
            metric: Distance metric (cosine, euclidean, dotproduct)
            embedding_generator: Optional embedding generator instance
        """
        self.api_key = api_key
        self.index_name = index_name
        self.environment = environment
        self.dimension = dimension
        self.metric = metric
        self.embedding_generator = embedding_generator

        # Initialize Pinecone client
        self.pc = Pinecone(api_key=api_key)

        # Initialize or connect to index
        self._initialize_index()

        logger.info(
            f"Initialized PineconeVectorStore: index={index_name}, "
            f"dim={dimension}, metric={metric}"
        )

    def _initialize_index(self):
        """Create or connect to the Pinecone index."""
        try:
            # Check if index exists
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]

            if self.index_name not in existing_indexes:
                logger.info(f"Creating new Pinecone index: {self.index_name}")

                # Create serverless index
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric=self.metric,
                    spec=ServerlessSpec(cloud="aws", region=self.environment),
                )

                # Wait for index to be ready
                self._wait_for_index_ready()

                logger.info(f"Successfully created index: {self.index_name}")
            else:
                logger.info(f"Connected to existing index: {self.index_name}")

            # Get index connection
            self.index = self.pc.Index(self.index_name)

        except Exception as e:
            logger.error(f"Failed to initialize Pinecone index: {e}")
            raise

    def _wait_for_index_ready(self, timeout: int = 300):
        """
        Wait for index to be ready.

        Args:
            timeout: Maximum wait time in seconds
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                index_stats = self.pc.describe_index(self.index_name)
                if index_stats.status.ready:
                    logger.info(f"Index {self.index_name} is ready")
                    return
            except Exception as e:
                logger.warning(f"Error checking index status: {e}")

            time.sleep(5)

        raise TimeoutError(f"Index {self.index_name} not ready after {timeout}s")

    async def upsert(
        self,
        documents: List[Dict[str, Any]],
        namespace: str = "",
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Upsert documents with embeddings to Pinecone.

        Args:
            documents: List of documents with 'id', 'text', and optional 'metadata'
            namespace: Optional namespace for multi-tenancy
            batch_size: Number of vectors per batch

        Returns:
            Upsert statistics

        Example:
            documents = [
                {
                    "id": "doc1",
                    "text": "This is the first document",
                    "metadata": {"category": "general", "timestamp": "2025-01-01"}
                },
                {
                    "id": "doc2",
                    "text": "This is the second document",
                    "metadata": {"category": "tech", "timestamp": "2025-01-02"}
                }
            ]
            stats = await store.upsert(documents)
        """
        if not self.embedding_generator:
            raise ValueError("EmbeddingGenerator not configured")

        try:
            # Generate embeddings for all documents
            texts = [doc["text"] for doc in documents]
            embeddings = await self.embedding_generator.generate_batch(texts)

            # Prepare vectors for upsert
            vectors = []
            for doc, embedding in zip(documents, embeddings):
                vector = {
                    "id": doc["id"],
                    "values": embedding,
                    "metadata": doc.get("metadata", {}),
                }
                vectors.append(vector)

            # Upsert in batches
            total_upserted = 0
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                result = self.index.upsert(vectors=batch, namespace=namespace)
                total_upserted += result.upserted_count

                logger.debug(f"Upserted batch {i//batch_size + 1}: {result.upserted_count} vectors")

            logger.info(
                f"Successfully upserted {total_upserted} vectors to namespace '{namespace}'"
            )

            return {
                "upserted_count": total_upserted,
                "namespace": namespace,
                "batch_count": (len(vectors) + batch_size - 1) // batch_size,
            }

        except Exception as e:
            logger.error(f"Failed to upsert documents: {e}")
            raise

    async def query(
        self,
        query_text: str,
        top_k: int = 5,
        namespace: str = "",
        filter: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
        include_values: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Query the vector store for similar documents.

        Args:
            query_text: Text to search for
            top_k: Number of results to return
            namespace: Optional namespace to search in
            filter: Optional metadata filter
            include_metadata: Include document metadata in results
            include_values: Include embedding values in results

        Returns:
            List of matching documents with scores

        Example:
            results = await store.query(
                query_text="machine learning algorithms",
                top_k=5,
                filter={"category": "tech"}
            )
        """
        if not self.embedding_generator:
            raise ValueError("EmbeddingGenerator not configured")

        try:
            # Generate query embedding
            query_embedding = await self.embedding_generator.generate(query_text)

            # Query Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                namespace=namespace,
                filter=filter,
                include_metadata=include_metadata,
                include_values=include_values,
            )

            # Format results
            matches = []
            for match in results.matches:
                result = {
                    "id": match.id,
                    "score": match.score,
                }

                if include_metadata and hasattr(match, "metadata"):
                    result["metadata"] = match.metadata

                if include_values and hasattr(match, "values"):
                    result["values"] = match.values

                matches.append(result)

            logger.info(f"Query returned {len(matches)} results from namespace '{namespace}'")

            return matches

        except Exception as e:
            logger.error(f"Failed to query vector store: {e}")
            raise

    async def delete(
        self,
        ids: Optional[List[str]] = None,
        namespace: str = "",
        filter: Optional[Dict[str, Any]] = None,
        delete_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Delete vectors from the index.

        Args:
            ids: List of vector IDs to delete
            namespace: Namespace to delete from
            filter: Metadata filter for conditional deletion
            delete_all: Delete all vectors in namespace (use with caution)

        Returns:
            Deletion statistics
        """
        try:
            if delete_all:
                logger.warning(f"Deleting ALL vectors from namespace '{namespace}'")
                self.index.delete(delete_all=True, namespace=namespace)
                return {"deleted": "all", "namespace": namespace}

            elif ids:
                logger.info(f"Deleting {len(ids)} vectors from namespace '{namespace}'")
                self.index.delete(ids=ids, namespace=namespace)
                return {"deleted_count": len(ids), "namespace": namespace}

            elif filter:
                logger.info(f"Deleting vectors with filter from namespace '{namespace}'")
                self.index.delete(filter=filter, namespace=namespace)
                return {"deleted": "filtered", "filter": filter, "namespace": namespace}

            else:
                raise ValueError("Must specify ids, filter, or delete_all=True")

        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}")
            raise

    def get_stats(self, namespace: str = "") -> Dict[str, Any]:
        """
        Get index statistics.

        Args:
            namespace: Optional namespace to get stats for

        Returns:
            Index statistics
        """
        try:
            stats = self.index.describe_index_stats()

            if namespace:
                namespace_stats = stats.namespaces.get(namespace, {})
                return {
                    "namespace": namespace,
                    "vector_count": namespace_stats.vector_count if namespace_stats else 0,
                    "dimension": self.dimension,
                }
            else:
                return {
                    "total_vector_count": stats.total_vector_count,
                    "dimension": stats.dimension,
                    "index_fullness": stats.index_fullness,
                    "namespaces": {ns: info.vector_count for ns, info in stats.namespaces.items()},
                }

        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            raise

    def close(self):
        """Clean up resources."""
        logger.info("Closing Pinecone vector store connection")
        # Pinecone client doesn't need explicit cleanup
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

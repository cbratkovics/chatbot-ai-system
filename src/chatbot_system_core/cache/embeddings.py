"""Embedding generation and similarity calculation for semantic caching."""

import hashlib
import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Embedding:
    """Represents a text embedding."""

    text: str
    vector: np.ndarray
    model: str = "mock-embedding-model"
    dimensions: int = 384

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "text": self.text,
            "vector": self.vector.tolist(),
            "model": self.model,
            "dimensions": self.dimensions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Embedding":
        """Create from dictionary."""
        return cls(
            text=data["text"],
            vector=np.array(data["vector"]),
            model=data.get("model", "mock-embedding-model"),
            dimensions=data.get("dimensions", 384),
        )


class EmbeddingGenerator:
    """Generates embeddings for text using various strategies."""

    def __init__(self, model: str = "mock-embedding-model", dimensions: int = 384):
        self.model = model
        self.dimensions = dimensions
        self._cache = {}  # Simple in-memory cache
        logger.info(f"Embedding generator initialized with model {model}")

    async def generate(self, text: str) -> Embedding:
        """Generate embedding for text."""
        # Check cache first
        if text in self._cache:
            return self._cache[text]

        # In production, this would call an embedding API
        # For now, create a deterministic mock embedding
        embedding_vector = self._create_mock_embedding(text)

        embedding = Embedding(
            text=text, vector=embedding_vector, model=self.model, dimensions=self.dimensions
        )

        # Cache the result
        self._cache[text] = embedding

        return embedding

    def _create_mock_embedding(self, text: str) -> np.ndarray:
        """Create a deterministic mock embedding from text."""
        # Use hash to create deterministic values
        text_hash = hashlib.sha256(text.encode()).digest()

        # Create embedding vector from hash bytes
        np.random.seed(int.from_bytes(text_hash[:4], "big"))
        embedding = np.random.randn(self.dimensions).astype(np.float32)

        # Normalize to unit vector
        embedding = embedding / np.linalg.norm(embedding)

        return embedding

    async def generate_batch(self, texts: list[str]) -> list[Embedding]:
        """Generate embeddings for multiple texts."""
        embeddings = []
        for text in texts:
            embedding = await self.generate(text)
            embeddings.append(embedding)
        return embeddings

    def clear_cache(self):
        """Clear the embedding cache."""
        self._cache.clear()
        logger.debug("Embedding cache cleared")


class SimilarityCalculator:
    """Calculates similarity between embeddings."""

    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        # Ensure vectors are normalized
        vec1_norm = vec1 / np.linalg.norm(vec1)
        vec2_norm = vec2 / np.linalg.norm(vec2)

        # Calculate dot product (cosine similarity for normalized vectors)
        similarity = np.dot(vec1_norm, vec2_norm)

        # Ensure result is in [-1, 1] range
        return float(np.clip(similarity, -1.0, 1.0))

    @staticmethod
    def euclidean_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate Euclidean distance between two vectors."""
        return float(np.linalg.norm(vec1 - vec2))

    @staticmethod
    def manhattan_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate Manhattan distance between two vectors."""
        return float(np.sum(np.abs(vec1 - vec2)))

    def find_most_similar(
        self,
        query_embedding: Embedding,
        candidate_embeddings: list[Embedding],
        threshold: float = 0.85,
        top_k: int = 5,
        metric: str = "cosine",
    ) -> list[tuple[Embedding, float]]:
        """Find most similar embeddings to query."""
        if not candidate_embeddings:
            return []

        # Choose similarity metric
        if metric == "cosine":
            similarity_fn = self.cosine_similarity
            reverse = True  # Higher is better
        elif metric == "euclidean":
            similarity_fn = self.euclidean_distance
            reverse = False  # Lower is better
        elif metric == "manhattan":
            similarity_fn = self.manhattan_distance
            reverse = False  # Lower is better
        else:
            raise ValueError(f"Unknown metric: {metric}")

        # Calculate similarities
        similarities = []
        for candidate in candidate_embeddings:
            score = similarity_fn(query_embedding.vector, candidate.vector)

            # Apply threshold for cosine similarity
            if metric == "cosine" and score >= threshold:
                similarities.append((candidate, score))
            elif metric != "cosine":
                similarities.append((candidate, score))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=reverse)

        # Return top k results
        return similarities[:top_k]

    def is_similar(
        self,
        embedding1: Embedding,
        embedding2: Embedding,
        threshold: float = 0.85,
        metric: str = "cosine",
    ) -> bool:
        """Check if two embeddings are similar."""
        if metric == "cosine":
            similarity = self.cosine_similarity(embedding1.vector, embedding2.vector)
            return similarity >= threshold
        elif metric == "euclidean":
            distance = self.euclidean_distance(embedding1.vector, embedding2.vector)
            return distance <= (1 - threshold) * 2  # Convert threshold
        elif metric == "manhattan":
            distance = self.manhattan_distance(embedding1.vector, embedding2.vector)
            return distance <= (1 - threshold) * embedding1.dimensions
        else:
            raise ValueError(f"Unknown metric: {metric}")

    def batch_similarity(
        self,
        query_embedding: Embedding,
        candidate_embeddings: list[Embedding],
        metric: str = "cosine",
    ) -> np.ndarray:
        """Calculate similarity scores for batch of candidates."""
        if not candidate_embeddings:
            return np.array([])

        # Stack candidate vectors
        candidate_matrix = np.stack([c.vector for c in candidate_embeddings])

        if metric == "cosine":
            # Normalize vectors
            query_norm = query_embedding.vector / np.linalg.norm(query_embedding.vector)
            candidate_norms = candidate_matrix / np.linalg.norm(
                candidate_matrix, axis=1, keepdims=True
            )

            # Calculate dot products
            similarities = np.dot(candidate_norms, query_norm)
            return similarities

        elif metric == "euclidean":
            # Calculate distances
            distances = np.linalg.norm(candidate_matrix - query_embedding.vector, axis=1)
            return distances

        elif metric == "manhattan":
            # Calculate Manhattan distances
            distances = np.sum(np.abs(candidate_matrix - query_embedding.vector), axis=1)
            return distances

        else:
            raise ValueError(f"Unknown metric: {metric}")

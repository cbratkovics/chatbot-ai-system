"""Embedding generation for vector search."""

from typing import List, Optional
import hashlib
import logging

import openai
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings using OpenAI's text-embedding-ada-002 model."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-ada-002",
        dimensions: int = 1536,
    ):
        """
        Initialize the embedding generator.

        Args:
            api_key: OpenAI API key
            model: Embedding model to use
            dimensions: Expected embedding dimensions
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions
        logger.info(f"Initialized EmbeddingGenerator with model={model}, dim={dimensions}")

    async def generate(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            List of embedding values

        Raises:
            Exception: If embedding generation fails
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            embedding = response.data[0].embedding

            if len(embedding) != self.dimensions:
                logger.warning(
                    f"Embedding dimension mismatch: expected {self.dimensions}, "
                    f"got {len(embedding)}"
                )

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    async def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            Exception: If embedding generation fails
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
            )

            embeddings = [item.embedding for item in response.data]

            logger.info(f"Generated {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise

    @staticmethod
    def compute_text_hash(text: str) -> str:
        """
        Compute a deterministic hash for text.

        Args:
            text: Input text

        Returns:
            MD5 hash of the text
        """
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    async def close(self):
        """Close the OpenAI client."""
        await self.client.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

"""Vector store module (Pinecone) — opt-in via ``ENABLE_VECTOR_SEARCH=true``.

Nothing here is imported unless the flag is on. Why: the demo must not pay for, wait
on, or crash because of a vector database it does not use. The implementation stays
in ``pinecone_store.py`` as a full-deployment artifact.
"""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .pinecone_store import PineconeVectorStore

__all__ = ["get_vector_store", "PineconeVectorStore", "EmbeddingGenerator"]


def get_vector_store(settings: Any) -> Optional["PineconeVectorStore"]:
    """Return a Pinecone store when the flag is on, otherwise None.

    Imports pinecone lazily so a disabled deployment never loads the SDK.
    """
    if not getattr(settings, "enable_vector_search", False):
        return None
    if not getattr(settings, "has_pinecone_key", False):
        raise RuntimeError("ENABLE_VECTOR_SEARCH=true but PINECONE_API_KEY is not set")
    from .pinecone_store import PineconeVectorStore

    return PineconeVectorStore(
        api_key=settings.pinecone_api_key.get_secret_value(),
        index_name=settings.pinecone_index_name,
        environment=settings.pinecone_environment,
        dimension=settings.pinecone_dimension,
        metric=settings.pinecone_metric,
    )


def __getattr__(name: str) -> Any:
    # Lazy attribute access keeps ``from chatbot_ai_system.vector_store import X`` working
    # for the full deployment without importing pinecone at package import time.
    if name == "PineconeVectorStore":
        from .pinecone_store import PineconeVectorStore

        return PineconeVectorStore
    if name == "EmbeddingGenerator":
        from .embeddings import EmbeddingGenerator

        return EmbeddingGenerator
    raise AttributeError(name)

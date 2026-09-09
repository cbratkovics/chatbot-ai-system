"""Embedding-based semantic match for the response cache (ADR 0007).

The exact-key lookup stays first and free. Only on an exact miss is the final user turn
embedded and compared, by cosine similarity, against an in-process index of prompts this
worker has already answered. Candidates are scoped to a *namespace*: same tenant, model,
temperature and identical prior conversation. Paraphrase matching therefore applies to the
current question only; the surrounding context must match exactly, so a long shared history
cannot drag an unrelated follow-up over the threshold.

The index is bounded (``SEMANTIC_CACHE_MAX_ENTRIES``, LRU) and lives in the worker process,
like the memory cache. Any embedding failure degrades the request to exact-match behaviour;
the telemetry says so (``cache.semantic = "unavailable"``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


@dataclass
class EmbeddingResult:
    """One embedding call: unit-normalised vector plus what it cost."""

    vector: np.ndarray
    tokens: int
    model: str
    latency_ms: float


class Embedder(Protocol):
    model: str

    async def embed(self, text: str) -> EmbeddingResult:
        ...


class OpenAIEmbedder:
    """Embeddings from OpenAI through the SDK that is already installed for chat."""

    def __init__(
        self, api_key: str, model: str = DEFAULT_EMBEDDING_MODEL, timeout_seconds: float = 5.0
    ) -> None:
        from openai import AsyncOpenAI  # already a dependency; imported here to keep boot lean

        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    async def embed(self, text: str) -> EmbeddingResult:
        started = time.perf_counter()
        response = await self._client.embeddings.create(model=self.model, input=text)
        vector = unit(np.asarray(response.data[0].embedding, dtype=np.float32))
        tokens = int(getattr(response.usage, "prompt_tokens", 0) or 0)
        return EmbeddingResult(
            vector=vector,
            tokens=tokens,
            model=self.model,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )


def unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def normalise(text: str) -> str:
    """Same normalisation the exact key uses: lower-case, collapse whitespace, strip trailing punctuation."""
    return " ".join((text or "").lower().split()).rstrip(".,;:!? ")


def split_context(messages: Sequence[Any]) -> Tuple[List[Dict[str, str]], Optional[str]]:
    """Return (all messages except the final user turn, that final user turn's text)."""
    items = [{"role": m.role, "content": m.content} for m in messages]
    for index in range(len(items) - 1, -1, -1):
        if items[index]["role"] == "user":
            return items[:index] + items[index + 1 :], items[index]["content"]
    return items, None


def namespace_for(
    tenant: str, model: str, temperature: float, context: Sequence[Dict[str, str]]
) -> str:
    """Candidates must share tenant, model, temperature and the exact prior conversation."""
    payload = {
        "tenant": tenant,
        "model": model.lower().strip(),
        "temperature": round(temperature, 2),
        "context": [{"role": m["role"], "content": normalise(m["content"])} for m in context],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]


@dataclass
class IndexEntry:
    namespace: str
    cache_key: str
    prompt: str
    vector: np.ndarray


@dataclass
class Match:
    cache_key: str
    prompt: str
    similarity: float


class SemanticIndex:
    """Bounded LRU of (namespace, cache key, prompt, vector) kept in the worker process."""

    def __init__(self, max_entries: int = 512) -> None:
        self.max_entries = max(1, max_entries)
        self._entries: "OrderedDict[str, IndexEntry]" = OrderedDict()

    def __len__(self) -> int:
        return len(self._entries)

    def add(self, namespace: str, cache_key: str, prompt: str, vector: np.ndarray) -> None:
        self._entries[cache_key] = IndexEntry(namespace, cache_key, normalise(prompt), unit(vector))
        self._entries.move_to_end(cache_key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def remove(self, cache_key: str) -> None:
        self._entries.pop(cache_key, None)

    def clear(self) -> None:
        self._entries.clear()

    def nearest(self, namespace: str, vector: np.ndarray) -> Optional[Match]:
        """Best candidate in the namespace regardless of threshold, or None when it is empty."""
        query = unit(vector)
        best: Optional[Match] = None
        for entry in self._entries.values():
            if entry.namespace != namespace:
                continue
            similarity = float(np.dot(entry.vector, query))
            if best is None or similarity > best.similarity:
                best = Match(entry.cache_key, entry.prompt, similarity)
        if best is not None:
            self._entries.move_to_end(best.cache_key)
            best.similarity = round(best.similarity, 4)
        return best

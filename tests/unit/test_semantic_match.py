"""Semantic cache (ADR 0007): exact-first, paraphrase HIT with real similarity, tenant and
context scoping, bounded index, and honest degradation when embeddings are unavailable."""

from typing import Dict

import numpy as np
import pytest
from fastapi.testclient import TestClient

from chatbot_ai_system.api import chat as chat_api
from chatbot_ai_system.cache.semantic_match import (
    EmbeddingResult,
    SemanticIndex,
    namespace_for,
    normalise,
    split_context,
    unit,
)
from chatbot_ai_system.providers.base import ChatMessage
from chatbot_ai_system.providers.catalog import estimate_cost_usd, estimate_embedding_cost_usd

E1 = unit(np.array([1.0, 0.0, 0.0], dtype=np.float32))
E2 = unit(np.array([0.0, 1.0, 0.0], dtype=np.float32))
PARAPHRASE = unit(np.array([0.95, 0.31, 0.0], dtype=np.float32))  # cos(E1, PARAPHRASE) ~ 0.95
NEAR = unit(np.array([0.70, 0.71, 0.0], dtype=np.float32))  # ~0.70: below any sane threshold

VECTORS: Dict[str, np.ndarray] = {
    "what does a semantic cache do": E1,
    "explain what semantic caching does": PARAPHRASE,
    "what does a semantic cache not do": NEAR,
    "name three failure modes of an llm call": E2,
}


class FakeEmbedder:
    model = "text-embedding-3-small"

    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    async def embed(self, text: str) -> EmbeddingResult:
        self.calls += 1
        if self.fail:
            raise RuntimeError("embedding API down")
        vector = VECTORS.get(normalise(text))
        if vector is None:
            rng = np.random.default_rng(abs(hash(text)) % 2**32)
            vector = unit(rng.standard_normal(3).astype(np.float32))
        return EmbeddingResult(vector=vector, tokens=7, model=self.model, latency_ms=1.0)


def body(prompt: str, history=None):
    messages = [*(history or []), {"role": "user", "content": prompt}]
    return {"model": "gpt-4o-mini", "messages": messages, "stream": False}


@pytest.fixture
def semantic(monkeypatch):
    """Flag on, fake embedder injected, threshold 0.85."""
    from chatbot_ai_system.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "semantic_cache_enabled", True)
    monkeypatch.setattr(settings, "semantic_cache_threshold", 0.85)
    fake = FakeEmbedder()
    chat_api.semantic_index = SemanticIndex(max_entries=8)
    chat_api.embedder = fake
    return fake


# --------------------------------------------------------------------------- pure index
def test_index_returns_nearest_within_namespace_only():
    index = SemanticIndex(max_entries=10)
    index.add("ns-a", "key-a", "what does a semantic cache do", E1)
    index.add("ns-b", "key-b", "same words, other tenant", E1)
    match = index.nearest("ns-a", PARAPHRASE)
    assert match is not None and match.cache_key == "key-a"
    assert match.similarity == pytest.approx(0.95, abs=0.01)
    assert index.nearest("ns-c", PARAPHRASE) is None


def test_index_is_bounded_lru():
    index = SemanticIndex(max_entries=2)
    for i in range(3):
        index.add("ns", f"k{i}", f"prompt {i}", unit(np.array([1.0, i, 0.0], dtype=np.float32)))
    assert len(index) == 2
    assert index.nearest("ns", unit(np.array([1.0, 0.0, 0.0], dtype=np.float32))).cache_key != "k0"


def test_split_context_isolates_the_final_user_turn():
    messages = [
        ChatMessage(role="system", content="be brief"),
        ChatMessage(role="user", content="hi"),
        ChatMessage(role="assistant", content="hello"),
        ChatMessage(role="user", content="What is P95?"),
    ]
    context, prompt = split_context(messages)
    assert prompt == "What is P95?"
    assert [m["role"] for m in context] == ["system", "user", "assistant"]
    same = namespace_for("public", "gpt-4o-mini", 0.7, context)
    assert same == namespace_for("public", "GPT-4o-mini", 0.7, context)
    assert same != namespace_for("acme", "gpt-4o-mini", 0.7, context)
    assert same != namespace_for("public", "gpt-4o-mini", 0.7, context[:-1])


# --------------------------------------------------------------------------- route
def test_paraphrase_is_a_semantic_hit_with_real_similarity(client: TestClient, fake_chat_provider, semantic):
    first = client.post("/api/v1/chat/completions", json=body("What does a semantic cache do?")).json()
    assert first["telemetry"]["cache"]["status"] == "miss"
    assert first["telemetry"]["cache"]["semantic"] == "miss"
    assert first["telemetry"]["embedding"]["tokens"] == 7

    second = client.post("/api/v1/chat/completions", json=body("Explain what semantic caching does")).json()
    t = second["telemetry"]
    assert t["cache"]["status"] == "hit" and t["cache"]["match"] == "semantic"
    assert t["cache"]["semantic"] == "hit" and t["cache"]["threshold"] == 0.85
    assert 0.9 < t["cache"]["similarity"] < 1.0
    assert t["cache"]["matched_key"] == first["cache_key"]
    assert second["choices"][0]["message"]["content"] == fake_chat_provider.reply
    assert fake_chat_provider.calls == 1  # provider not called for the paraphrase
    # A semantic hit pays for its embedding and nothing else; the avoided cost is the list price.
    assert t["cost_usd"] == estimate_embedding_cost_usd("text-embedding-3-small", 7)
    assert t["cost_avoided_usd"] == estimate_cost_usd("gpt-4o-mini", 5, 3)
    assert second["similarity_score"] == t["cache"]["similarity"]


def test_exact_repeat_skips_the_embedding_call(client: TestClient, fake_chat_provider, semantic):
    client.post("/api/v1/chat/completions", json=body("What does a semantic cache do?"))
    assert semantic.calls == 1
    t = client.post("/api/v1/chat/completions", json=body("what does a semantic cache do")).json()["telemetry"]
    assert t["cache"]["status"] == "hit" and t["cache"]["match"] == "exact"
    assert t["cache"]["semantic"] == "not_needed" and t["cost_usd"] == 0.0
    assert semantic.calls == 1


def test_below_threshold_is_a_miss_that_reports_the_nearest_candidate(client: TestClient, fake_chat_provider, semantic):
    client.post("/api/v1/chat/completions", json=body("What does a semantic cache do?"))
    t = client.post("/api/v1/chat/completions", json=body("What does a semantic cache NOT do?")).json()["telemetry"]
    assert t["cache"]["status"] == "miss" and t["cache"]["match"] is None
    assert t["cache"]["semantic"] == "miss"
    assert 0.6 < t["cache"]["similarity"] < 0.85  # nearest candidate, shown so the miss is explainable
    assert t["cache"]["nearest_key"] and t["cache"]["matched_key"] is None
    assert fake_chat_provider.calls == 2


def test_context_and_tenant_scope_the_match(client: TestClient, fake_chat_provider, semantic):
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    client.post("/api/v1/chat/completions", json=body("What does a semantic cache do?", history))
    # Same question, different prior conversation: not a candidate.
    t = client.post("/api/v1/chat/completions", json=body("Explain what semantic caching does")).json()["telemetry"]
    assert t["cache"]["status"] == "miss" and t["cache"]["similarity"] is None
    # Same conversation, other tenant: not a candidate either.
    t = client.post(
        "/api/v1/chat/completions",
        json=body("Explain what semantic caching does", history),
        headers={"X-Tenant-ID": "acme"},
    ).json()["telemetry"]
    assert t["cache"]["status"] == "miss" and t["cache"]["similarity"] is None
    # Same conversation, same tenant: hit.
    t = client.post("/api/v1/chat/completions", json=body("Explain what semantic caching does", history)).json()["telemetry"]
    assert t["cache"]["status"] == "hit" and t["cache"]["match"] == "semantic"


def test_embedding_failure_degrades_to_exact_match_and_says_so(client: TestClient, fake_chat_provider, semantic):
    client.post("/api/v1/chat/completions", json=body("What does a semantic cache do?"))
    semantic.fail = True
    t = client.post("/api/v1/chat/completions", json=body("Explain what semantic caching does")).json()["telemetry"]
    assert t["cache"]["status"] == "miss" and t["cache"]["match"] is None
    assert t["cache"]["semantic"] == "unavailable"
    assert t["embedding"]["cost_usd"] == 0.0
    assert fake_chat_provider.calls == 2
    # Exact repeats still hit while embeddings are down.
    t = client.post("/api/v1/chat/completions", json=body("What does a semantic cache do?")).json()["telemetry"]
    assert t["cache"]["status"] == "hit" and t["cache"]["match"] == "exact"


def test_semantic_hit_streams_meta_delta_done(client: TestClient, fake_chat_provider, semantic):
    from tests.unit.test_streaming_sse import parse_sse

    client.post("/api/v1/chat/completions", json=body("What does a semantic cache do?"))
    with client.stream("POST", "/api/v1/chat/completions", json={**body("Explain what semantic caching does"), "stream": True}) as res:
        events = parse_sse(res.read().decode())
    assert [e["event"] for e in events] == ["meta", "delta", "done"]
    assert events[0]["data"]["cache"]["match"] == "semantic"
    assert events[-1]["data"]["cache"]["status"] == "hit" and events[-1]["data"]["cost_avoided_usd"] > 0


def test_health_reports_semantic_cache_state(client: TestClient, semantic):
    sem = client.get("/api/v1/chat/health").json()["semantic_cache"]
    assert sem["enabled"] is True and sem["backend"] == "openai-embeddings"
    assert sem["threshold"] == 0.85 and sem["index_entries"] == 0 and sem["max_entries"] == 8


def test_health_when_disabled(client: TestClient):
    sem = client.get("/api/v1/chat/health").json()["semantic_cache"]
    assert sem == {
        "enabled": False, "backend": None, "embedding_model": None,
        "threshold": None, "index_entries": 0, "max_entries": 512,
    }

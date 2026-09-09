"""Cost estimate: list prices per model, None for unknown models, zero on cache hits."""

from chatbot_ai_system.providers.catalog import (
    MODEL_CATALOG,
    MODEL_PRICES,
    estimate_cost_usd,
    estimate_embedding_cost_usd,
    price_model_for,
)


def test_every_catalogue_model_has_a_price():
    assert set(MODEL_CATALOG) <= set(MODEL_PRICES)


def test_estimate_matches_list_price_arithmetic():
    # gpt-4o-mini: $0.15 in / $0.60 out per 1M tokens
    assert estimate_cost_usd("gpt-4o-mini", 1_000_000, 0) == 0.15
    assert estimate_cost_usd("gpt-4o-mini", 0, 1_000_000) == 0.60
    assert estimate_cost_usd("gpt-4o-mini", 1000, 500) == round((1000 * 0.15 + 500 * 0.60) / 1e6, 8)


def test_unknown_model_has_no_estimate():
    assert estimate_cost_usd("made-up", 10, 10) is None


def test_token_estimate_is_monotonic_and_never_zero_for_text():
    from chatbot_ai_system.api.chat import estimate_tokens

    assert estimate_tokens("") == 0
    short, long = estimate_tokens("hello"), estimate_tokens("hello " * 50)
    assert 0 < short < long


def test_dated_snapshot_ids_are_priced_as_their_alias():
    # OpenAI answers "gpt-4o-mini" requests with the snapshot id it actually served.
    assert price_model_for("gpt-4o-mini-2024-07-18") == "gpt-4o-mini"
    assert price_model_for("gpt-4o-2024-11-20") == "gpt-4o"
    assert price_model_for("claude-sonnet-4-5-20250929") == "claude-sonnet-4-5"
    assert estimate_cost_usd("gpt-4o-mini-2024-07-18", 1000, 500) == estimate_cost_usd("gpt-4o-mini", 1000, 500)
    assert price_model_for("gpt-5-nano") is None


def test_embedding_cost_is_list_price_per_token():
    assert estimate_embedding_cost_usd("text-embedding-3-small", 1_000_000) == 0.02
    assert estimate_embedding_cost_usd("text-embedding-3-small", 10) == 2e-7
    assert estimate_embedding_cost_usd("unknown-embedding", 10) is None

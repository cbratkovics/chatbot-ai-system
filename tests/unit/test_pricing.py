"""Cost estimate: list prices per model, None for unknown models, zero on cache hits."""

from chatbot_ai_system.providers.catalog import MODEL_CATALOG, MODEL_PRICES, estimate_cost_usd


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

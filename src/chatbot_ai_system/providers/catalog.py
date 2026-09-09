"""Single source of truth for which model belongs to which provider.

Why: the model list used to live in three places and had drifted (retired Claude 2
models, no gpt-4o-mini). One table, imported everywhere.
"""

import re
from typing import Dict, List, Optional

# model id -> provider name
MODEL_CATALOG: Dict[str, str] = {
    # OpenAI
    "gpt-4o-mini": "openai",
    "gpt-4o": "openai",
    "gpt-4.1-mini": "openai",
    # Anthropic
    "claude-3-5-haiku-latest": "anthropic",
    "claude-sonnet-4-5": "anthropic",
    # Groq (OpenAI-compatible endpoint, free tier)
    "llama-3.1-8b-instant": "groq",
    "llama-3.3-70b-versatile": "groq",
}

PROVIDERS: List[str] = ["openai", "anthropic", "groq"]

# Retired or renamed model ids still found in old env files and clients. They resolve to
# the current equivalent so a stale DEFAULT_MODEL does not 404 every request; the
# response reports the model that actually answered.
LEGACY_ALIASES: Dict[str, str] = {
    "gpt-3.5-turbo": "gpt-4o-mini",
    "gpt-3.5-turbo-16k": "gpt-4o-mini",
    "gpt-4": "gpt-4o",
    "gpt-4-turbo-preview": "gpt-4o",
    "gpt-4-1106-preview": "gpt-4o",
    "gpt-4-0125-preview": "gpt-4o",
    "claude-3-haiku-20240307": "claude-3-5-haiku-latest",
    "claude-3-sonnet-20240229": "claude-sonnet-4-5",
    "claude-3-opus-20240229": "claude-sonnet-4-5",
}


def resolve_model(model: str) -> str:
    """Map a legacy id to its current replacement; unknown ids pass through unchanged."""
    return LEGACY_ALIASES.get(model, model)


def provider_for(model: str) -> Optional[str]:
    """Return the provider that serves ``model`` or None."""
    return MODEL_CATALOG.get(model)


def models_for(provider: str) -> List[str]:
    """All catalogued models for one provider, in catalogue order."""
    return [m for m, p in MODEL_CATALOG.items() if p == provider]


# List prices in USD per 1M tokens (input, output), as published by each provider at the time
# of writing. Used only for the per-message cost estimate shown in the UI; verify before billing.
MODEL_PRICES: Dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "claude-3-5-haiku-latest": (0.80, 4.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
}


_SNAPSHOT_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")


def price_model_for(model: str) -> Optional[str]:
    """Catalogue id whose list price applies to ``model``.

    Providers answer with dated snapshot ids (``gpt-4o-mini-2024-07-18``) that are billed as the
    alias they belong to. Exact match first, then the id with a trailing date removed, then the
    longest catalogue id that prefixes it. None when nothing applies.
    """
    if model in MODEL_PRICES:
        return model
    undated = _SNAPSHOT_SUFFIX.sub("", model)
    if undated in MODEL_PRICES:
        return undated
    prefixes = [m for m in MODEL_PRICES if model.startswith(m + "-")]
    return max(prefixes, key=len) if prefixes else None


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    """Estimated USD cost of one call, or None when the model has no price entry."""
    priced = price_model_for(model)
    prices = MODEL_PRICES.get(priced) if priced else None
    if prices is None:
        return None
    price_in, price_out = prices
    return round((prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000, 8)


# Embedding list prices in USD per 1M input tokens. Used for the semantic-cache lookup cost
# that a semantic HIT still pays (ADR 0007).
EMBEDDING_PRICES: Dict[str, float] = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
}


def estimate_embedding_cost_usd(model: str, tokens: int) -> Optional[float]:
    """Estimated USD cost of one embedding call, or None when the model has no price entry."""
    price = EMBEDDING_PRICES.get(model)
    if price is None:
        return None
    return round(tokens * price / 1_000_000, 10)

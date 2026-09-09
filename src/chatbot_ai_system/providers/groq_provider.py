"""Groq provider.

Groq exposes an OpenAI-compatible endpoint, so this is the OpenAI provider with a
different base URL and name. Why: zero new dependencies for a free-tier fallback.
"""

from typing import Optional

from .catalog import models_for
from .openai_provider import OpenAIProvider


class GroqProvider(OpenAIProvider):
    """OpenAI-compatible client pointed at Groq."""

    PROVIDER_NAME = "groq"
    DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
    SUPPORTED_MODELS = models_for("groq")

    # openai/gpt-oss-* are reasoning models: their reasoning tokens count against max_tokens, and
    # at the demo's 400-token cap "medium" effort can consume the whole budget and return no
    # content at all (evals/results/latest.md, failover eval, 2026-09-09). Low effort keeps the
    # answer short, cheap and present.
    REASONING_EFFORT = "low"

    def __init__(
        self,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 2,
        base_url: Optional[str] = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            base_url=base_url or self.DEFAULT_BASE_URL,
        )

    @staticmethod
    def _is_reasoning_model(model: str) -> bool:
        return model.startswith("openai/gpt-oss")

    def _with_reasoning(self, model: str, kwargs: dict) -> dict:
        if self._is_reasoning_model(model):
            kwargs.setdefault("reasoning_effort", self.REASONING_EFFORT)
        return kwargs

    async def chat(self, messages, model, temperature=0.7, max_tokens=None, **kwargs):
        return await super().chat(
            messages, model, temperature, max_tokens, **self._with_reasoning(model, kwargs)
        )

    async def stream(self, messages, model, temperature=0.7, max_tokens=None, **kwargs):
        async for chunk in super().stream(
            messages, model, temperature, max_tokens, **self._with_reasoning(model, kwargs)
        ):
            yield chunk

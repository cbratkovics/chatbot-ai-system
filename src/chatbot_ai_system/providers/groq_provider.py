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

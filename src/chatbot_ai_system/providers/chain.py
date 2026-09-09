"""Provider failover chain.

Tries the provider that owns the requested model, then each configured fallback, and
records every attempt so the response can show what happened. Why: "automatic
failover" was a README claim with no code behind it on the request path.

Failover triggers: 401, 402, 429, 5xx, timeouts, connection errors, and unknown
models. Non-failover: a 4xx the caller can fix (bad request, content filter).
"""

import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Sequence, Tuple, Union

from .base import (
    AuthenticationError,
    BaseProvider,
    ChatMessage,
    ChatResponse,
    ContentFilterError,
    ModelNotFoundError,
    ProviderError,
    QuotaExceededError,
    RateLimitError,
    StreamChunk,
    TimeoutError,
)
from .catalog import provider_for

logger = logging.getLogger(__name__)

ProviderFactory = Callable[[str], BaseProvider]


@dataclass
class Attempt:
    """One try against one provider/model."""

    provider: str
    model: str
    outcome: str  # "ok" | "failed" | "skipped"
    status_code: Optional[int] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StreamStart:
    """First item yielded by ``ProviderChain.stream``: which provider/model is answering."""

    provider: str
    model: str


SIMULATED_OUTAGE = "simulated_outage"


class ChainExhaustedError(ProviderError):
    """Every candidate failed. Carries the attempt log and the primary error."""

    def __init__(self, attempts: List[Attempt], primary_error: ProviderError):
        summary = "; ".join(
            f"{a.provider}/{a.model}: {a.outcome}"
            + (f" ({a.status_code} {a.error_code})" if a.error_code else "")
            for a in attempts
        )
        super().__init__(
            f"All providers failed. {primary_error.message} [{summary}]",
            provider=primary_error.provider,
            status_code=primary_error.status_code,
            error_code="all_providers_failed",
            retryable=False,
        )
        self.attempts = attempts
        self.primary_error = primary_error


def should_failover(exc: ProviderError) -> bool:
    """Decide whether an error is worth trying the next provider for."""
    if isinstance(
        exc,
        (AuthenticationError, QuotaExceededError, RateLimitError, TimeoutError, ModelNotFoundError),
    ):
        return True
    if isinstance(exc, ContentFilterError):
        return False
    if exc.status_code is None:
        return True  # connection-level failure
    return exc.status_code >= 500


_CODES = (
    (AuthenticationError, "auth_error"),
    (QuotaExceededError, "quota_exhausted"),
    (RateLimitError, "rate_limited"),
    (TimeoutError, "timeout"),
    (ModelNotFoundError, "model_not_found"),
    (ContentFilterError, "content_filtered"),
)


def _error_code(exc: ProviderError) -> str:
    if exc.error_code:
        return exc.error_code
    for cls, code in _CODES:
        if isinstance(exc, cls):
            return code
    return "provider_error"


class ProviderChain:
    """Ordered provider/model candidates with per-request attempt logging."""

    def __init__(
        self,
        make_provider: ProviderFactory,
        fallbacks: Sequence[Tuple[str, str]] = (),
        simulate_primary_failure: bool = False,
    ) -> None:
        self._make_provider = make_provider
        self._fallbacks = list(fallbacks)
        # Demo switch: the first candidate "fails" with a 503 before it is ever called, so an
        # interviewer can watch failover happen without touching a real provider.
        self.simulate_primary_failure = simulate_primary_failure

    def _simulated_failure(self, provider_name: str, model: str) -> Tuple[Attempt, ProviderError]:
        exc = ProviderError(
            f"Simulated outage of {provider_name} (demo toggle)",
            provider=provider_name,
            status_code=503,
            error_code=SIMULATED_OUTAGE,
        )
        attempt = Attempt(
            provider=provider_name,
            model=model,
            outcome="failed",
            status_code=503,
            error_code=SIMULATED_OUTAGE,
            message=exc.message,
        )
        return attempt, exc

    def candidates(self, model: str) -> List[Tuple[str, str]]:
        """Primary (provider, model) followed by fallbacks, de-duplicated."""
        primary = provider_for(model)
        ordered: List[Tuple[str, str]] = []
        if primary:
            ordered.append((primary, model))
        for pair in self._fallbacks:
            if pair not in ordered:
                ordered.append(pair)
        return ordered

    async def complete(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Tuple[ChatResponse, List[Attempt]]:
        attempts: List[Attempt] = []
        first_failure: Optional[ProviderError] = None  # a provider was called and failed
        first_skip: Optional[ProviderError] = None  # a provider could not be built (no key)

        candidates = self.candidates(model)
        if not candidates:
            raise ModelNotFoundError(
                f"Model '{model}' is not in the catalogue", provider=None, status_code=404
            )

        for index, (provider_name, candidate_model) in enumerate(candidates):
            started = time.perf_counter()
            if index == 0 and self.simulate_primary_failure:
                attempt, exc = self._simulated_failure(provider_name, candidate_model)
                attempts.append(attempt)
                first_failure = exc
                logger.warning("Simulated outage of %s/%s (demo toggle)", provider_name, candidate_model)
                continue
            try:
                provider = self._make_provider(provider_name)
            except ProviderError as exc:
                # Typically "no API key configured": skip, do not count as a failure.
                attempts.append(
                    Attempt(
                        provider=provider_name,
                        model=candidate_model,
                        outcome="skipped",
                        status_code=exc.status_code,
                        error_code=_error_code(exc),
                        message=exc.message,
                    )
                )
                if first_skip is None:
                    first_skip = exc
                continue

            try:
                response = await provider.chat(
                    messages=messages,
                    model=candidate_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                latency = (time.perf_counter() - started) * 1000
                attempts.append(
                    Attempt(
                        provider=provider_name,
                        model=candidate_model,
                        outcome="ok",
                        latency_ms=round(latency, 1),
                    )
                )
                return response, attempts
            except ProviderError as exc:
                latency = (time.perf_counter() - started) * 1000
                attempts.append(
                    Attempt(
                        provider=provider_name,
                        model=candidate_model,
                        outcome="failed",
                        status_code=exc.status_code,
                        error_code=_error_code(exc),
                        message=exc.message,
                        latency_ms=round(latency, 1),
                    )
                )
                if first_failure is None:
                    first_failure = exc
                if not should_failover(exc):
                    raise
                logger.warning(
                    "Failing over from %s/%s after %s: %s",
                    provider_name,
                    candidate_model,
                    _error_code(exc),
                    exc.message,
                )

        # Report the most informative error: a real upstream failure beats "no key".
        primary_error = first_failure or first_skip
        assert primary_error is not None
        raise ChainExhaustedError(attempts, primary_error)

    async def stream(
        self,
        messages: List[ChatMessage],
        model: str,
        attempts: List[Attempt],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Union[StreamStart, StreamChunk]]:
        """Stream from the first provider that produces a first chunk.

        Failover happens only *before* the first chunk: once tokens have been sent to the
        client, switching providers would splice two answers together. ``attempts`` is
        filled in place because async generators cannot return a value.
        """
        first_failure: Optional[ProviderError] = None
        first_skip: Optional[ProviderError] = None

        candidates = self.candidates(model)
        if not candidates:
            raise ModelNotFoundError(
                f"Model '{model}' is not in the catalogue", provider=None, status_code=404
            )

        for index, (provider_name, candidate_model) in enumerate(candidates):
            started = time.perf_counter()
            if index == 0 and self.simulate_primary_failure:
                attempt, exc = self._simulated_failure(provider_name, candidate_model)
                attempts.append(attempt)
                first_failure = exc
                logger.warning("Simulated outage of %s/%s (demo toggle)", provider_name, candidate_model)
                continue
            try:
                provider = self._make_provider(provider_name)
            except ProviderError as exc:
                attempts.append(
                    Attempt(
                        provider=provider_name,
                        model=candidate_model,
                        outcome="skipped",
                        status_code=exc.status_code,
                        error_code=_error_code(exc),
                        message=exc.message,
                    )
                )
                if first_skip is None:
                    first_skip = exc
                continue

            generator = provider.stream(
                messages=messages,
                model=candidate_model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            try:
                first_chunk: Optional[StreamChunk] = await generator.__anext__()
            except StopAsyncIteration:
                first_chunk = None
            except ProviderError as exc:
                latency = (time.perf_counter() - started) * 1000
                attempts.append(
                    Attempt(
                        provider=provider_name,
                        model=candidate_model,
                        outcome="failed",
                        status_code=exc.status_code,
                        error_code=_error_code(exc),
                        message=exc.message,
                        latency_ms=round(latency, 1),
                    )
                )
                if first_failure is None:
                    first_failure = exc
                if not should_failover(exc):
                    raise
                logger.warning(
                    "Failing over stream from %s/%s after %s: %s",
                    provider_name,
                    candidate_model,
                    _error_code(exc),
                    exc.message,
                )
                continue

            yield StreamStart(provider=provider_name, model=candidate_model)
            if first_chunk is not None:
                yield first_chunk
                try:
                    async for chunk in generator:
                        yield chunk
                except ProviderError as exc:
                    latency = (time.perf_counter() - started) * 1000
                    attempts.append(
                        Attempt(
                            provider=provider_name,
                            model=candidate_model,
                            outcome="failed",
                            status_code=exc.status_code,
                            error_code=_error_code(exc),
                            message=f"stream interrupted: {exc.message}",
                            latency_ms=round(latency, 1),
                        )
                    )
                    raise
            latency = (time.perf_counter() - started) * 1000
            attempts.append(
                Attempt(
                    provider=provider_name,
                    model=candidate_model,
                    outcome="ok",
                    latency_ms=round(latency, 1),
                )
            )
            return

        primary_error = first_failure or first_skip
        assert primary_error is not None
        raise ChainExhaustedError(attempts, primary_error)

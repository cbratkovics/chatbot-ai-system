"""Base provider interface and common functionality."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


class ProviderStatus(str, Enum):
    """Provider health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        retryable: bool = True,
        provider_name: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.retryable = retryable
        self.provider_name = provider_name


class RateLimitError(ProviderError):
    """Rate limit exceeded error."""

    def __init__(
        self, message: str, retry_after: int | None = None, provider_name: str | None = None
    ):
        super().__init__(
            message, error_code="rate_limit", retryable=True, provider_name=provider_name
        )
        self.retry_after = retry_after


class QuotaExceededError(ProviderError):
    """Quota exceeded error."""

    def __init__(self, message: str, provider_name: str | None = None):
        super().__init__(
            message, error_code="quota_exceeded", retryable=False, provider_name=provider_name
        )


class AuthenticationError(ProviderError):
    """Authentication failed error."""

    def __init__(self, message: str, provider_name: str | None = None):
        super().__init__(
            message, error_code="authentication", retryable=False, provider_name=provider_name
        )


class ModelNotFoundError(ProviderError):
    """Model not found error."""

    def __init__(self, message: str, model: str, provider_name: str | None = None):
        super().__init__(
            message, error_code="model_not_found", retryable=False, provider_name=provider_name
        )
        self.model = model


class ContentFilterError(ProviderError):
    """Content filter violation error."""

    def __init__(self, message: str, provider_name: str | None = None):
        super().__init__(
            message, error_code="content_filter", retryable=False, provider_name=provider_name
        )


@dataclass
class TokenUsage:
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @property
    def prompt_cost(self) -> float:
        """Calculate prompt cost (override in provider implementations)."""
        return 0.0

    @property
    def completion_cost(self) -> float:
        """Calculate completion cost (override in provider implementations)."""
        return 0.0

    @property
    def total_cost(self) -> float:
        """Calculate total cost."""
        return self.prompt_cost + self.completion_cost


@dataclass
class CompletionResponse:
    """Response from a completion request."""

    id: UUID
    content: str
    model: str
    usage: TokenUsage
    provider: str
    latency_ms: float
    cached: bool = False
    finish_reason: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class StreamChunk:
    """A chunk of streaming response."""

    id: UUID
    delta: str
    finish_reason: str | None = None
    chunk_index: int = 0
    metadata: dict[str, Any] | None = None


@dataclass
class Message:
    """Chat message."""

    role: str  # "system", "user", "assistant"
    content: str
    metadata: dict[str, Any] | None = None


@dataclass
class CompletionRequest:
    """Request for completion."""

    messages: list[Message]
    model: str
    temperature: float = 0.7
    max_tokens: int | None = 1000
    stream: bool = False

    # Advanced parameters
    top_p: float | None = 1.0
    frequency_penalty: float | None = 0.0
    presence_penalty: float | None = 0.0
    stop: list[str] | None = None

    # Context
    conversation_id: UUID | None = None
    tenant_id: UUID = None
    user_id: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class ProviderConfig:
    """Provider configuration."""

    name: str
    api_key: str
    base_url: str | None = None
    timeout: int = 30
    max_retries: int = 3
    max_concurrent_requests: int = 10

    # Circuit breaker configuration
    circuit_breaker_threshold: int = 5  # Failures before opening
    circuit_breaker_timeout: int = 60  # Seconds before half-open
    circuit_breaker_half_open_requests: int = 3  # Requests to test in half-open

    # Cost configuration (per 1K tokens)
    prompt_cost_per_1k: float = 0.0015  # Default GPT-3.5 pricing
    completion_cost_per_1k: float = 0.002

    # Model configuration
    supported_models: list[str] = field(default_factory=list)
    default_model: str = "default"
    max_context_length: int = 4000

    # Health check configuration
    health_check_interval: int = 30  # Seconds between health checks
    health_check_timeout: int = 5  # Health check timeout

    def __post_init__(self):
        if not self.supported_models:
            self.supported_models = [self.default_model]


class ProviderMetrics:
    """Metrics tracking for a provider."""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.reset()

    def reset(self):
        """Reset all metrics."""
        self.requests_total = 0
        self.requests_successful = 0
        self.requests_failed = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.total_latency = 0.0
        self.error_counts = {}
        self.last_request_time = None
        self.last_error_time = None
        self.last_error = None

    def record_request(
        self,
        success: bool,
        latency_ms: float,
        tokens: int = 0,
        cost: float = 0.0,
        error: Exception | None = None,
    ):
        """Record a request metric."""
        self.requests_total += 1
        self.last_request_time = time.time()
        self.total_latency += latency_ms
        self.total_tokens += tokens
        self.total_cost += cost

        if success:
            self.requests_successful += 1
        else:
            self.requests_failed += 1
            if error:
                error_type = type(error).__name__
                self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
                self.last_error_time = time.time()
                self.last_error = str(error)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.requests_total == 0:
            return 1.0
        return self.requests_successful / self.requests_total

    @property
    def average_latency(self) -> float:
        """Calculate average latency."""
        if self.requests_total == 0:
            return 0.0
        return self.total_latency / self.requests_total

    @property
    def status(self) -> ProviderStatus:
        """Determine provider status based on metrics."""
        # If no recent requests, consider offline
        if self.last_request_time is None:
            return ProviderStatus.OFFLINE

        # Check if last request was recent (within 5 minutes)
        if time.time() - self.last_request_time > 300:
            return ProviderStatus.OFFLINE

        # Check success rate
        if self.success_rate < 0.5:
            return ProviderStatus.UNHEALTHY
        elif self.success_rate < 0.8:
            return ProviderStatus.DEGRADED

        # Check latency (if average > 5 seconds, degraded)
        if self.average_latency > 5000:
            return ProviderStatus.DEGRADED

        return ProviderStatus.HEALTHY


@runtime_checkable
class ProviderProtocol(Protocol):
    """Protocol defining the provider interface."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...
    async def complete_stream(
        self, request: CompletionRequest
    ) -> AsyncIterator[StreamChunk]: ...
    async def health_check(self) -> dict[str, Any]: ...
    def supports_model(self, model: str) -> bool: ...
    def is_healthy(self) -> bool: ...


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker implementation for provider resilience."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.success_count = 0
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise ProviderError(
                        f"Circuit breaker is OPEN for {self.config.name}",
                        error_code="circuit_open",
                        retryable=True,
                        provider_name=self.config.name,
                    )

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.circuit_breaker_half_open_requests:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    logger.info(f"Circuit breaker for {self.config.name} is now CLOSED")
            elif self.state == CircuitBreakerState.CLOSED:
                self.failure_count = 0

    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
                logger.warning(
                    f"Circuit breaker for {self.config.name} is OPEN (half-open test failed)"
                )
            elif (
                self.state == CircuitBreakerState.CLOSED
                and self.failure_count >= self.config.circuit_breaker_threshold
            ):
                self.state = CircuitBreakerState.OPEN
                logger.warning(
                    f"Circuit breaker for {self.config.name} is OPEN "
                    f"(threshold {self.config.circuit_breaker_threshold} reached)"
                )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True
        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure > timedelta(seconds=self.config.circuit_breaker_timeout)

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        return self.state == CircuitBreakerState.OPEN

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
        }


class BaseProvider(ABC):
    """Base class for all providers."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.metrics = ProviderMetrics(config.name)
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        self.circuit_breaker = CircuitBreaker(config)
        self._last_health_check: datetime | None = None
        self._health_check_result: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        """Get provider name."""
        return self.config.name

    @property
    def status(self) -> ProviderStatus:
        """Get provider status."""
        return self.metrics.status

    def is_healthy(self) -> bool:
        """Check if provider is healthy."""
        return self.status in [ProviderStatus.HEALTHY, ProviderStatus.DEGRADED]

    @abstractmethod
    async def _make_request(self, request: CompletionRequest) -> CompletionResponse:
        """Make the actual API request (implemented by subclasses)."""
        pass

    @abstractmethod
    async def _make_stream_request(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Make streaming API request (implemented by subclasses)."""
        pass

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Complete a chat request with retry logic and circuit breaker."""
        if request.stream:
            raise ValueError("Use complete_stream() for streaming requests")

        async def _make_request_with_circuit_breaker():
            async with self._semaphore:  # Rate limit concurrent requests
                start_time = time.time()

                try:
                    response = await asyncio.wait_for(
                        self._make_request(request), timeout=self.config.timeout
                    )

                    # Record successful request
                    latency_ms = (time.time() - start_time) * 1000
                    self.metrics.record_request(
                        success=True,
                        latency_ms=latency_ms,
                        tokens=response.usage.total_tokens,
                        cost=response.usage.total_cost,
                    )

                    response.latency_ms = latency_ms
                    response.provider = self.name

                    return response

                except Exception as e:
                    # Record failed request
                    latency_ms = (time.time() - start_time) * 1000
                    self.metrics.record_request(success=False, latency_ms=latency_ms, error=e)

                    # Convert to appropriate ProviderError if needed
                    if not isinstance(e, ProviderError):
                        if isinstance(e, asyncio.TimeoutError):
                            raise ProviderError(
                                f"Request timeout after {self.config.timeout}s",
                                error_code="timeout",
                                retryable=True,
                                provider_name=self.name,
                            ) from e
                        else:
                            raise ProviderError(
                                f"Request failed: {str(e)}",
                                error_code="unknown",
                                retryable=True,
                                provider_name=self.name,
                            ) from e

                    # Add provider name if not set
                    if not e.provider_name:
                        e.provider_name = self.name

                    raise

        # Apply retry logic with exponential backoff and jitter
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((ProviderError, asyncio.TimeoutError)),
            stop=stop_after_attempt(self.config.max_retries),
            wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
            reraise=True,
        ):
            with attempt:
                # Apply circuit breaker
                return await self.circuit_breaker.call(_make_request_with_circuit_breaker)

    async def complete_stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Complete a streaming chat request."""
        if not request.stream:
            raise ValueError("Use complete() for non-streaming requests")

        async with self._semaphore:
            start_time = time.time()
            chunk_count = 0
            total_tokens = 0

            try:
                async for chunk in self._make_stream_request(request):
                    chunk_count += 1
                    yield chunk

                # Record successful streaming request
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_request(
                    success=True,
                    latency_ms=latency_ms,
                    tokens=total_tokens,  # Would need to track this in implementation
                )

            except Exception as e:
                # Record failed request
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record_request(success=False, latency_ms=latency_ms, error=e)

                if not isinstance(e, ProviderError):
                    raise ProviderError(
                        f"Streaming request failed: {str(e)}",
                        error_code="stream_error",
                        retryable=False,
                        provider_name=self.name,
                    ) from e

                raise

    def supports_model(self, model: str) -> bool:
        """Check if provider supports a specific model."""
        return model in self.config.supported_models

    def calculate_cost(self, usage: TokenUsage) -> TokenUsage:
        """Calculate cost for token usage."""
        usage.prompt_cost = (usage.prompt_tokens / 1000) * self.config.prompt_cost_per_1k
        usage.completion_cost = (
            usage.completion_tokens / 1000
        ) * self.config.completion_cost_per_1k
        return usage

    async def health_check(self, force: bool = False) -> dict[str, Any]:
        """Perform health check with caching."""
        now = datetime.now()
        
        # Return cached result if available and not forced
        if (
            not force
            and self._last_health_check
            and self._health_check_result
            and (now - self._last_health_check).seconds < self.config.health_check_interval
        ):
            return self._health_check_result

        # Perform actual health check
        try:
            # Try a minimal request to verify connectivity
            test_request = CompletionRequest(
                messages=[Message(role="user", content="test")],
                model=self.config.default_model,
                max_tokens=1,
            )
            
            # Use shorter timeout for health check
            original_timeout = self.config.timeout
            self.config.timeout = self.config.health_check_timeout
            
            try:
                await asyncio.wait_for(
                    self._make_request(test_request),
                    timeout=self.config.health_check_timeout,
                )
                health_status = ProviderStatus.HEALTHY
            except Exception:
                health_status = self.status  # Use metrics-based status
            finally:
                self.config.timeout = original_timeout
                
        except Exception as e:
            logger.warning(f"Health check failed for {self.name}: {e}")
            health_status = ProviderStatus.UNHEALTHY

        self._health_check_result = {
            "provider": self.name,
            "status": health_status.value,
            "circuit_breaker": self.circuit_breaker.get_status(),
            "metrics": {
                "success_rate": round(self.metrics.success_rate, 3),
                "average_latency_ms": round(self.metrics.average_latency, 2),
                "total_requests": self.metrics.requests_total,
                "total_tokens": self.metrics.total_tokens,
                "total_cost": round(self.metrics.total_cost, 4),
                "error_counts": self.metrics.error_counts,
                "last_request_time": self.metrics.last_request_time,
                "last_error": self.metrics.last_error,
            },
            "config": {
                "supported_models": self.config.supported_models,
                "concurrent_limit": self.config.max_concurrent_requests,
                "timeout": self.config.timeout,
                "max_retries": self.config.max_retries,
            },
            "timestamp": now.isoformat(),
        }
        
        self._last_health_check = now
        return self._health_check_result

    async def reset_circuit_breaker(self):
        """Manually reset the circuit breaker."""
        async with self.circuit_breaker._lock:
            self.circuit_breaker.state = CircuitBreakerState.CLOSED
            self.circuit_breaker.failure_count = 0
            self.circuit_breaker.success_count = 0
            logger.info(f"Circuit breaker for {self.name} manually reset")

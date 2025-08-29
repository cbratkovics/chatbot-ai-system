"""Fallback manager for automatic failover between models and providers."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class FallbackReason(Enum):
    """Reasons for fallback."""

    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    QUOTA_EXCEEDED = "quota_exceeded"
    MODEL_UNAVAILABLE = "model_unavailable"
    QUALITY_ISSUE = "quality_issue"
    COST_LIMIT = "cost_limit"


@dataclass
class FallbackChain:
    """Chain of fallback options."""

    primary: tuple[str, str]  # (provider, model)
    fallbacks: list[tuple[str, str]]  # [(provider, model), ...]
    max_attempts: int = 3
    retry_delay_ms: int = 1000
    exponential_backoff: bool = True


@dataclass
class FallbackEvent:
    """Record of a fallback event."""

    timestamp: datetime
    from_provider: str
    from_model: str
    to_provider: str | None
    to_model: str | None
    reason: FallbackReason
    error_message: str | None
    attempt_number: int
    success: bool


class FallbackManager:
    """Manages automatic failover between models and providers."""

    def __init__(self):
        """Initialize fallback manager."""
        self.fallback_chains: dict[str, FallbackChain] = {}
        self.fallback_history: list[FallbackEvent] = []
        self.provider_health: dict[str, float] = {}  # provider -> health score
        self.circuit_breakers: dict[str, CircuitBreaker] = {}

    def register_fallback_chain(self, name: str, chain: FallbackChain):
        """Register a fallback chain.

        Args:
            name: Chain name
            chain: Fallback chain configuration
        """
        self.fallback_chains[name] = chain
        logger.info(f"Registered fallback chain: {name}")

    async def execute_with_fallback(
        self,
        request_func: Callable,
        chain_name: str,
        request_args: dict[str, Any],
        validation_func: Callable | None = None,
    ) -> tuple[Any, FallbackEvent | None]:
        """Execute request with automatic fallback.

        Args:
            request_func: Function to execute request
            chain_name: Name of fallback chain to use
            request_args: Arguments for request function
            validation_func: Optional function to validate response

        Returns:
            Tuple of (response, fallback_event)
        """
        if chain_name not in self.fallback_chains:
            raise ValueError(f"Unknown fallback chain: {chain_name}")

        chain = self.fallback_chains[chain_name]
        models_to_try = [chain.primary] + chain.fallbacks

        last_error = None
        attempt = 0

        for provider, model in models_to_try:
            attempt += 1

            if attempt > chain.max_attempts:
                break

            # Check circuit breaker
            breaker_key = f"{provider}:{model}"
            if breaker_key in self.circuit_breakers:
                if not self.circuit_breakers[breaker_key].is_closed():
                    logger.info(f"Circuit breaker open for {breaker_key}, skipping")
                    continue

            try:
                # Calculate delay with exponential backoff
                if attempt > 1:
                    delay = chain.retry_delay_ms / 1000
                    if chain.exponential_backoff:
                        delay *= 2 ** (attempt - 2)
                    await asyncio.sleep(delay)

                # Attempt request
                logger.info(f"Attempting request with {provider}:{model} (attempt {attempt})")

                response = await asyncio.wait_for(
                    request_func(provider=provider, model=model, **request_args),
                    timeout=30,  # 30 second timeout
                )

                # Validate response if validation function provided
                if validation_func:
                    is_valid = await validation_func(response)
                    if not is_valid:
                        raise ValueError("Response validation failed")

                # Success - record if it was a fallback
                if attempt > 1:
                    event = FallbackEvent(
                        timestamp=datetime.utcnow(),
                        from_provider=models_to_try[attempt - 2][0],
                        from_model=models_to_try[attempt - 2][1],
                        to_provider=provider,
                        to_model=model,
                        reason=self._determine_fallback_reason(last_error),
                        error_message=str(last_error) if last_error else None,
                        attempt_number=attempt,
                        success=True,
                    )
                    self._record_event(event)
                    return response, event

                # Primary success
                self._update_provider_health(provider, True)
                return response, None

            except TimeoutError:
                last_error = "Request timeout"
                logger.error(f"Timeout for {provider}:{model}")
                self._update_provider_health(provider, False)
                self._trigger_circuit_breaker(breaker_key, FallbackReason.TIMEOUT)

            except Exception as e:
                last_error = e
                logger.error(f"Error with {provider}:{model}: {e}")
                self._update_provider_health(provider, False)

                # Determine reason and trigger circuit breaker if needed
                reason = self._determine_fallback_reason(e)
                self._trigger_circuit_breaker(breaker_key, reason)

        # All attempts failed
        event = FallbackEvent(
            timestamp=datetime.utcnow(),
            from_provider=models_to_try[-1][0] if models_to_try else None,
            from_model=models_to_try[-1][1] if models_to_try else None,
            to_provider=None,
            to_model=None,
            reason=self._determine_fallback_reason(last_error),
            error_message=str(last_error) if last_error else None,
            attempt_number=attempt,
            success=False,
        )
        self._record_event(event)

        raise Exception(f"All fallback attempts failed: {last_error}")

    def _determine_fallback_reason(self, error: Any) -> FallbackReason:
        """Determine fallback reason from error.

        Args:
            error: Error that occurred

        Returns:
            Fallback reason
        """
        if error is None:
            return FallbackReason.PROVIDER_ERROR

        error_str = str(error).lower()

        if "timeout" in error_str:
            return FallbackReason.TIMEOUT
        elif "rate" in error_str or "limit" in error_str:
            return FallbackReason.RATE_LIMIT
        elif "quota" in error_str or "exceeded" in error_str:
            return FallbackReason.QUOTA_EXCEEDED
        elif "not found" in error_str or "unavailable" in error_str:
            return FallbackReason.MODEL_UNAVAILABLE
        elif "quality" in error_str or "validation" in error_str:
            return FallbackReason.QUALITY_ISSUE
        elif "cost" in error_str:
            return FallbackReason.COST_LIMIT
        else:
            return FallbackReason.PROVIDER_ERROR

    def _update_provider_health(self, provider: str, success: bool):
        """Update provider health score.

        Args:
            provider: Provider name
            success: Whether request succeeded
        """
        if provider not in self.provider_health:
            self.provider_health[provider] = 1.0

        # Exponential moving average
        alpha = 0.1
        if success:
            self.provider_health[provider] = min(
                1.0, self.provider_health[provider] * (1 - alpha) + alpha
            )
        else:
            self.provider_health[provider] = max(0.0, self.provider_health[provider] * (1 - alpha))

    def _trigger_circuit_breaker(self, key: str, reason: FallbackReason):
        """Trigger circuit breaker for provider/model.

        Args:
            key: Provider:model key
            reason: Reason for triggering
        """
        if key not in self.circuit_breakers:
            self.circuit_breakers[key] = CircuitBreaker(
                failure_threshold=3, recovery_timeout=60, expected_exception=Exception
            )

        self.circuit_breakers[key].record_failure()

    def _record_event(self, event: FallbackEvent):
        """Record fallback event.

        Args:
            event: Fallback event
        """
        self.fallback_history.append(event)

        # Keep only recent history
        if len(self.fallback_history) > 10000:
            self.fallback_history = self.fallback_history[-5000:]

        # Log event
        if event.success:
            logger.info(
                f"Fallback succeeded: {event.from_provider}:{event.from_model} -> "
                f"{event.to_provider}:{event.to_model} (reason: {event.reason.value})"
            )
        else:
            logger.error(
                f"All fallbacks failed for {event.from_provider}:{event.from_model} "
                f"(reason: {event.reason.value})"
            )

    def get_provider_health(self) -> dict[str, float]:
        """Get provider health scores.

        Returns:
            Provider health scores
        """
        return self.provider_health.copy()

    def get_fallback_stats(self) -> dict[str, Any]:
        """Get fallback statistics.

        Returns:
            Fallback statistics
        """
        if not self.fallback_history:
            return {
                "total_fallbacks": 0,
                "success_rate": 0,
                "reasons": {},
                "provider_health": self.provider_health,
            }

        total = len(self.fallback_history)
        successful = sum(1 for e in self.fallback_history if e.success)

        # Count reasons
        reasons = {}
        for event in self.fallback_history:
            reason = event.reason.value
            reasons[reason] = reasons.get(reason, 0) + 1

        # Recent fallback rate (last hour)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_fallbacks = [e for e in self.fallback_history if e.timestamp > one_hour_ago]

        return {
            "total_fallbacks": total,
            "successful_fallbacks": successful,
            "success_rate": successful / total if total > 0 else 0,
            "reasons": reasons,
            "recent_fallbacks_per_hour": len(recent_fallbacks),
            "provider_health": self.provider_health,
            "open_circuit_breakers": [
                key for key, breaker in self.circuit_breakers.items() if not breaker.is_closed()
            ],
        }

    def create_adaptive_chain(
        self, primary_model: tuple[str, str], available_models: list[tuple[str, str]]
    ) -> FallbackChain:
        """Create adaptive fallback chain based on health scores.

        Args:
            primary_model: Primary provider and model
            available_models: Available fallback options

        Returns:
            Adaptive fallback chain
        """
        # Score and sort fallback options
        scored_models = []
        for provider, model in available_models:
            if (provider, model) == primary_model:
                continue

            # Calculate score based on health and circuit breaker status
            score = self.provider_health.get(provider, 0.5)

            breaker_key = f"{provider}:{model}"
            if breaker_key in self.circuit_breakers:
                if not self.circuit_breakers[breaker_key].is_closed():
                    score = 0  # Skip if circuit breaker is open

            scored_models.append(((provider, model), score))

        # Sort by score (highest first)
        scored_models.sort(key=lambda x: x[1], reverse=True)

        # Select top fallbacks
        fallbacks = [model for model, score in scored_models[:3] if score > 0.2]

        return FallbackChain(
            primary=primary_model,
            fallbacks=fallbacks,
            max_attempts=len(fallbacks) + 1,
            retry_delay_ms=1000,
            exponential_backoff=True,
        )


class CircuitBreaker:
    """Circuit breaker for provider/model combinations."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open

    def is_closed(self) -> bool:
        """Check if circuit breaker is closed (allowing requests).

        Returns:
            True if closed
        """
        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if recovery timeout has passed
            if self.last_failure_time:
                time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds()

                if time_since_failure > self.recovery_timeout:
                    self.state = "half_open"
                    return True

            return False

        # Half open - allow one request
        return True

    def record_success(self):
        """Record successful request."""
        if self.state == "half_open":
            # Recovery successful
            self.state = "closed"
            self.failure_count = 0
            logger.info("Circuit breaker closed after successful recovery")

    def record_failure(self):
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            if self.state != "open":
                self.state = "open"
                logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
        elif self.state == "half_open":
            # Failed during recovery
            self.state = "open"
            logger.warning("Circuit breaker reopened after failed recovery")

    def get_state(self) -> dict[str, Any]:
        """Get circuit breaker state.

        Returns:
            State information
        """
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "recovery_timeout": self.recovery_timeout,
        }

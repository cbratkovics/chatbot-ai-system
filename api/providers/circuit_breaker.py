"""Circuit breaker pattern implementation for provider resilience."""

import asyncio
import logging
import time
from collections.abc import Callable
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, message: str, state: str, failure_count: int):
        super().__init__(message)
        self.state = state
        self.failure_count = failure_count


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting against cascading failures.

    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are blocked
    - HALF_OPEN: Testing if service has recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type[Exception] = Exception,
        half_open_max_calls: int = 3,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery (seconds)
            expected_exception: Exception type that triggers circuit breaker
            half_open_max_calls: Max calls to allow in half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.half_open_max_calls = half_open_max_calls

        # State tracking
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None
        self.state = CircuitBreakerState.CLOSED

        # Half-open state tracking
        self.half_open_calls = 0

        # Metrics
        self.total_calls = 0
        self.blocked_calls = 0

        # Thread safety
        self._lock = asyncio.Lock()

        logger.debug(
            f"Circuit breaker initialized: threshold={failure_threshold}, timeout={recovery_timeout}s"
        )

    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is closed (normal operation)."""
        return self.state == CircuitBreakerState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open (blocking requests)."""
        return self.state == CircuitBreakerState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open (testing recovery)."""
        return self.state == CircuitBreakerState.HALF_OPEN

    def should_allow_request(self) -> bool:
        """Determine if a request should be allowed through."""
        current_time = time.time()

        if self.is_closed:
            return True

        if self.is_open:
            # Check if recovery timeout has passed
            if (
                self.last_failure_time
                and current_time - self.last_failure_time >= self.recovery_timeout
            ):
                logger.info("Circuit breaker transitioning to half-open for recovery testing")
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False

        if self.is_half_open:
            # Allow limited requests to test recovery
            return self.half_open_calls < self.half_open_max_calls

        return False

    def record_success(self):
        """Record a successful operation."""
        if self.is_half_open:
            self.success_count += 1
            self.half_open_calls += 1

            # If we've had enough successful calls, close the circuit
            if self.success_count >= self.half_open_max_calls:
                logger.info("Circuit breaker closing after successful recovery")
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.half_open_calls = 0

        elif self.is_closed:
            # Reset failure count on successful operation
            if self.failure_count > 0:
                self.failure_count = 0

    def record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.is_half_open:
            logger.warning("Circuit breaker opening due to failure during recovery test")
            self.state = CircuitBreakerState.OPEN
            self.success_count = 0
            self.half_open_calls = 0

        elif self.is_closed and self.failure_count >= self.failure_threshold:
            logger.warning(f"Circuit breaker opening after {self.failure_count} failures")
            self.state = CircuitBreakerState.OPEN

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit breaker is open
            Exception: Any exception from the wrapped function
        """
        async with self._lock:
            self.total_calls += 1

            if not self.should_allow_request():
                self.blocked_calls += 1
                raise CircuitBreakerError(
                    f"Circuit breaker is {self.state.value}, blocking request",
                    self.state.value,
                    self.failure_count,
                )

            if self.is_half_open:
                self.half_open_calls += 1

        # Execute function outside of lock to avoid blocking other requests
        start_time = time.time()

        try:
            # Handle both sync and async functions
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Record success
            async with self._lock:
                self.record_success()

            execution_time = (time.time() - start_time) * 1000
            logger.debug(f"Circuit breaker: successful call in {execution_time:.2f}ms")

            return result

        except self.expected_exception as e:
            # Record failure for expected exceptions
            async with self._lock:
                self.record_failure()

            execution_time = (time.time() - start_time) * 1000
            logger.warning(f"Circuit breaker: failed call in {execution_time:.2f}ms - {str(e)}")

            raise

        except Exception as e:
            # Don't trigger circuit breaker for unexpected exceptions
            logger.error(f"Circuit breaker: unexpected exception - {str(e)}")
            raise

    def reset(self):
        """Reset circuit breaker to closed state."""
        with self._lock:
            logger.info("Circuit breaker manually reset to closed state")
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.half_open_calls = 0
            self.last_failure_time = None

    def force_open(self):
        """Force circuit breaker to open state."""
        with self._lock:
            logger.warning("Circuit breaker manually forced to open state")
            self.state = CircuitBreakerState.OPEN
            self.last_failure_time = time.time()

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "blocked_calls": self.blocked_calls,
            "last_failure_time": self.last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "half_open_calls": self.half_open_calls,
            "half_open_max_calls": self.half_open_max_calls,
        }

    def __str__(self) -> str:
        """String representation of circuit breaker state."""
        return (
            f"CircuitBreaker(state={self.state.value}, "
            f"failures={self.failure_count}/{self.failure_threshold}, "
            f"total_calls={self.total_calls}, "
            f"blocked_calls={self.blocked_calls})"
        )


class AsyncCircuitBreaker(CircuitBreaker):
    """Async-optimized circuit breaker with better async/await support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        """Async context manager entry."""
        await self._lock.acquire()

        if not self.should_allow_request():
            self._lock.release()
            raise CircuitBreakerError(
                f"Circuit breaker is {self.state.value}", self.state.value, self.failure_count
            )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        try:
            if exc_type and issubclass(exc_type, self.expected_exception):
                self.record_failure()
            elif exc_type is None:
                self.record_success()
        finally:
            self._lock.release()

        # Don't suppress exceptions
        return False

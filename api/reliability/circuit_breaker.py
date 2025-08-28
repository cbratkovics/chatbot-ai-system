"""Advanced circuit breaker implementation with Hystrix-style patterns."""

import asyncio
import logging
import statistics
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitMetrics:
    """Metrics for circuit breaker decisions."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_requests: int = 0
    consecutive_failures: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    response_times: deque = None
    error_percentages: deque = None

    def __post_init__(self):
        if self.response_times is None:
            self.response_times = deque(maxlen=100)
        if self.error_percentages is None:
            self.error_percentages = deque(maxlen=10)


class HystrixCircuitBreaker:
    """Hystrix-style circuit breaker with advanced features."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        failure_percentage_threshold: float = 50.0,
        timeout_ms: int = 5000,
        recovery_timeout_ms: int = 60000,
        rolling_window_ms: int = 10000,
        min_requests_in_window: int = 20,
        sleep_window_ms: int = 5000,
    ):
        """Initialize circuit breaker.

        Args:
            name: Circuit breaker name
            failure_threshold: Consecutive failures to open circuit
            failure_percentage_threshold: Error percentage to open circuit
            timeout_ms: Request timeout in milliseconds
            recovery_timeout_ms: Time before attempting recovery
            rolling_window_ms: Time window for metrics
            min_requests_in_window: Minimum requests for percentage calculation
            sleep_window_ms: Sleep time when circuit is open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.failure_percentage_threshold = failure_percentage_threshold
        self.timeout_ms = timeout_ms
        self.recovery_timeout_ms = recovery_timeout_ms
        self.rolling_window_ms = rolling_window_ms
        self.min_requests_in_window = min_requests_in_window
        self.sleep_window_ms = sleep_window_ms

        self.state = CircuitState.CLOSED
        self.metrics = CircuitMetrics()
        self.state_changed_at = datetime.utcnow()
        self.rolling_window = deque(maxlen=1000)  # Store recent requests

        # Callbacks
        self.on_open_callback = None
        self.on_close_callback = None
        self.on_half_open_callback = None

    async def call(
        self, func: Callable, *args, fallback: Callable | None = None, **kwargs
    ) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function arguments
            fallback: Fallback function if circuit is open
            **kwargs: Function keyword arguments

        Returns:
            Function result or fallback result
        """
        # Check if circuit allows request
        if not self._can_attempt_request():
            if fallback:
                logger.info(f"Circuit {self.name} is open, using fallback")
                return await self._execute_fallback(fallback, *args, **kwargs)
            else:
                raise CircuitOpenException(f"Circuit {self.name} is open")

        # Execute request with timeout
        start_time = time.time()

        try:
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.timeout_ms / 1000)

            # Record success
            response_time = (time.time() - start_time) * 1000
            await self._record_success(response_time)

            return result

        except TimeoutError:
            # Record timeout
            await self._record_timeout()

            if fallback:
                return await self._execute_fallback(fallback, *args, **kwargs)
            else:
                raise CircuitTimeoutException(f"Request timed out after {self.timeout_ms}ms") from None

        except Exception:
            # Record failure
            await self._record_failure()

            if fallback:
                return await self._execute_fallback(fallback, *args, **kwargs)
            else:
                raise

    def _can_attempt_request(self) -> bool:
        """Check if request can be attempted.

        Returns:
            True if request is allowed
        """
        current_state = self._get_current_state()

        if current_state == CircuitState.CLOSED:
            return True
        elif current_state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._should_attempt_recovery():
                self._transition_to_half_open()
                return True
            return False
        else:  # HALF_OPEN
            # Allow limited requests for testing
            return True

    def _get_current_state(self) -> CircuitState:
        """Get current circuit state.

        Returns:
            Current state
        """
        # Update state based on metrics if needed
        if self.state == CircuitState.CLOSED:
            if self._should_open_circuit():
                self._transition_to_open()

        return self.state

    def _should_open_circuit(self) -> bool:
        """Check if circuit should open.

        Returns:
            True if circuit should open
        """
        # Check consecutive failures
        if self.metrics.consecutive_failures >= self.failure_threshold:
            return True

        # Check error percentage in rolling window
        recent_requests = self._get_recent_requests()
        if len(recent_requests) >= self.min_requests_in_window:
            error_count = sum(1 for r in recent_requests if not r["success"])
            error_percentage = (error_count / len(recent_requests)) * 100

            if error_percentage >= self.failure_percentage_threshold:
                return True

        return False

    def _should_attempt_recovery(self) -> bool:
        """Check if recovery should be attempted.

        Returns:
            True if should attempt recovery
        """
        time_in_open = (datetime.utcnow() - self.state_changed_at).total_seconds() * 1000
        return time_in_open >= self.recovery_timeout_ms

    def _get_recent_requests(self) -> list[dict[str, Any]]:
        """Get requests in rolling window.

        Returns:
            Recent requests
        """
        current_time = time.time() * 1000
        window_start = current_time - self.rolling_window_ms

        return [r for r in self.rolling_window if r["timestamp"] >= window_start]

    async def _record_success(self, response_time_ms: float):
        """Record successful request.

        Args:
            response_time_ms: Response time in milliseconds
        """
        self.metrics.total_requests += 1
        self.metrics.successful_requests += 1
        self.metrics.consecutive_failures = 0
        self.metrics.last_success_time = datetime.utcnow()
        self.metrics.response_times.append(response_time_ms)

        # Add to rolling window
        self.rolling_window.append(
            {"timestamp": time.time() * 1000, "success": True, "response_time": response_time_ms}
        )

        # Handle state transitions
        if self.state == CircuitState.HALF_OPEN:
            # Successful test, close circuit
            self._transition_to_closed()

        # Update error percentage
        self._update_error_percentage()

    async def _record_failure(self):
        """Record failed request."""
        self.metrics.total_requests += 1
        self.metrics.failed_requests += 1
        self.metrics.consecutive_failures += 1
        self.metrics.last_failure_time = datetime.utcnow()

        # Add to rolling window
        self.rolling_window.append(
            {"timestamp": time.time() * 1000, "success": False, "response_time": None}
        )

        # Handle state transitions
        if self.state == CircuitState.HALF_OPEN:
            # Failed test, reopen circuit
            self._transition_to_open()

        # Update error percentage
        self._update_error_percentage()

    async def _record_timeout(self):
        """Record timeout request."""
        self.metrics.total_requests += 1
        self.metrics.timeout_requests += 1
        self.metrics.consecutive_failures += 1
        self.metrics.last_failure_time = datetime.utcnow()

        # Add to rolling window
        self.rolling_window.append(
            {
                "timestamp": time.time() * 1000,
                "success": False,
                "response_time": self.timeout_ms,
                "timeout": True,
            }
        )

        # Handle state transitions
        if self.state == CircuitState.HALF_OPEN:
            # Timeout during test, reopen circuit
            self._transition_to_open()

        # Update error percentage
        self._update_error_percentage()

    def _update_error_percentage(self):
        """Update rolling error percentage."""
        recent = self._get_recent_requests()
        if recent:
            errors = sum(1 for r in recent if not r["success"])
            percentage = (errors / len(recent)) * 100
            self.metrics.error_percentages.append(percentage)

    def _transition_to_open(self):
        """Transition to open state."""
        if self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            self.state_changed_at = datetime.utcnow()

            logger.warning(f"Circuit {self.name} opened")

            if self.on_open_callback:
                asyncio.create_task(self.on_open_callback(self))

    def _transition_to_closed(self):
        """Transition to closed state."""
        if self.state != CircuitState.CLOSED:
            self.state = CircuitState.CLOSED
            self.state_changed_at = datetime.utcnow()
            self.metrics.consecutive_failures = 0

            logger.info(f"Circuit {self.name} closed")

            if self.on_close_callback:
                asyncio.create_task(self.on_close_callback(self))

    def _transition_to_half_open(self):
        """Transition to half-open state."""
        if self.state != CircuitState.HALF_OPEN:
            self.state = CircuitState.HALF_OPEN
            self.state_changed_at = datetime.utcnow()

            logger.info(f"Circuit {self.name} half-open for testing")

            if self.on_half_open_callback:
                asyncio.create_task(self.on_half_open_callback(self))

    async def _execute_fallback(self, fallback: Callable, *args, **kwargs) -> Any:
        """Execute fallback function.

        Args:
            fallback: Fallback function
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Fallback result
        """
        try:
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            else:
                return fallback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Fallback failed for circuit {self.name}: {e}")
            raise

    def reset(self):
        """Reset circuit breaker to initial state."""
        self.state = CircuitState.CLOSED
        self.metrics = CircuitMetrics()
        self.state_changed_at = datetime.utcnow()
        self.rolling_window.clear()

        logger.info(f"Circuit {self.name} reset")

    def get_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics.

        Returns:
            Metrics dictionary
        """
        success_rate = 0
        if self.metrics.total_requests > 0:
            success_rate = (self.metrics.successful_requests / self.metrics.total_requests) * 100

        avg_response_time = 0
        if self.metrics.response_times:
            avg_response_time = statistics.mean(self.metrics.response_times)

        current_error_percentage = 0
        if self.metrics.error_percentages:
            current_error_percentage = self.metrics.error_percentages[-1]

        return {
            "name": self.name,
            "state": self.state.value,
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "timeout_requests": self.metrics.timeout_requests,
            "success_rate": success_rate,
            "consecutive_failures": self.metrics.consecutive_failures,
            "avg_response_time_ms": avg_response_time,
            "current_error_percentage": current_error_percentage,
            "last_failure": self.metrics.last_failure_time.isoformat()
            if self.metrics.last_failure_time
            else None,
            "last_success": self.metrics.last_success_time.isoformat()
            if self.metrics.last_success_time
            else None,
            "time_in_state_ms": (datetime.utcnow() - self.state_changed_at).total_seconds() * 1000,
        }


class CircuitBreakerManager:
    """Manages multiple circuit breakers."""

    def __init__(self):
        """Initialize circuit breaker manager."""
        self.circuit_breakers: dict[str, HystrixCircuitBreaker] = {}

    def get_or_create(self, name: str, **config) -> HystrixCircuitBreaker:
        """Get or create circuit breaker.

        Args:
            name: Circuit breaker name
            **config: Configuration parameters

        Returns:
            Circuit breaker instance
        """
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = HystrixCircuitBreaker(name=name, **config)

        return self.circuit_breakers[name]

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all circuit breakers.

        Returns:
            All circuit breaker metrics
        """
        return {name: cb.get_metrics() for name, cb in self.circuit_breakers.items()}

    def get_open_circuits(self) -> list[str]:
        """Get list of open circuits.

        Returns:
            Names of open circuits
        """
        return [name for name, cb in self.circuit_breakers.items() if cb.state == CircuitState.OPEN]

    def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            cb.reset()

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on all circuits.

        Returns:
            Health check results
        """
        total_circuits = len(self.circuit_breakers)
        open_circuits = self.get_open_circuits()

        # Calculate aggregate metrics
        total_requests = sum(cb.metrics.total_requests for cb in self.circuit_breakers.values())

        total_failures = sum(cb.metrics.failed_requests for cb in self.circuit_breakers.values())

        return {
            "healthy": len(open_circuits) == 0,
            "total_circuits": total_circuits,
            "open_circuits": open_circuits,
            "open_circuit_count": len(open_circuits),
            "total_requests": total_requests,
            "total_failures": total_failures,
            "overall_success_rate": (
                ((total_requests - total_failures) / total_requests * 100)
                if total_requests > 0
                else 100
            ),
        }


class CircuitOpenException(Exception):
    """Exception raised when circuit is open."""

    pass


class CircuitTimeoutException(Exception):
    """Exception raised when request times out."""

    pass


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()

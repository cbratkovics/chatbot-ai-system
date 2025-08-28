"""Timeout management with cascading timeouts and deadline propagation."""

import asyncio
import logging
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# Context variable for deadline propagation
deadline_context: ContextVar[float | None] = ContextVar("deadline", default=None)


@dataclass
class TimeoutConfig:
    """Configuration for timeout behavior."""

    default_timeout_ms: float = 30000
    min_timeout_ms: float = 100
    max_timeout_ms: float = 300000
    cascade_reduction_factor: float = 0.9
    deadline_buffer_ms: float = 100


@dataclass
class TimeoutEvent:
    """Record of a timeout event."""

    timestamp: datetime
    operation: str
    timeout_ms: float
    actual_duration_ms: float | None
    timed_out: bool
    error: str | None


class TimeoutManager:
    """Manages timeouts with cascading and deadline propagation."""

    def __init__(self, config: TimeoutConfig | None = None):
        """Initialize timeout manager.

        Args:
            config: Timeout configuration
        """
        self.config = config or TimeoutConfig()
        self.timeout_events: list[TimeoutEvent] = []
        self.operation_timeouts: dict[str, float] = {}

    async def execute_with_timeout(
        self,
        func: Callable,
        *args,
        timeout_ms: float | None = None,
        operation: str = "unknown",
        propagate_deadline: bool = True,
        **kwargs,
    ) -> Any:
        """Execute function with timeout.

        Args:
            func: Function to execute
            timeout_ms: Timeout in milliseconds
            operation: Operation name for tracking
            propagate_deadline: Whether to propagate deadline
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        # Calculate effective timeout
        effective_timeout = self._calculate_effective_timeout(
            timeout_ms, operation, propagate_deadline
        )

        # Set deadline in context if propagating
        if propagate_deadline:
            deadline = time.time() + (effective_timeout / 1000)
            deadline_context.set(deadline)

        start_time = time.time()

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self._execute_function(func, *args, **kwargs), timeout=effective_timeout / 1000
            )

            # Record successful execution
            duration = (time.time() - start_time) * 1000
            self._record_event(
                operation=operation,
                timeout_ms=effective_timeout,
                actual_duration_ms=duration,
                timed_out=False,
            )

            # Update operation timeout statistics
            self._update_operation_timeout(operation, duration)

            return result

        except TimeoutError:
            # Record timeout
            duration = (time.time() - start_time) * 1000
            self._record_event(
                operation=operation,
                timeout_ms=effective_timeout,
                actual_duration_ms=duration,
                timed_out=True,
                error="Operation timed out",
            )

            logger.error(f"Operation '{operation}' timed out after {effective_timeout}ms")

            raise TimeoutException(f"Operation '{operation}' timed out after {effective_timeout}ms") from None

        finally:
            # Clear deadline context
            if propagate_deadline:
                deadline_context.set(None)

    def _calculate_effective_timeout(
        self, requested_timeout: float | None, operation: str, propagate_deadline: bool
    ) -> float:
        """Calculate effective timeout considering all factors.

        Args:
            requested_timeout: Requested timeout
            operation: Operation name
            propagate_deadline: Whether to consider propagated deadline

        Returns:
            Effective timeout in milliseconds
        """
        # Start with requested or default timeout
        timeout = requested_timeout or self.config.default_timeout_ms

        # Apply min/max bounds
        timeout = max(self.config.min_timeout_ms, timeout)
        timeout = min(self.config.max_timeout_ms, timeout)

        # Consider propagated deadline
        if propagate_deadline:
            deadline = deadline_context.get()
            if deadline:
                remaining = (deadline - time.time()) * 1000

                # Apply cascade reduction
                remaining *= self.config.cascade_reduction_factor

                # Ensure minimum buffer
                remaining -= self.config.deadline_buffer_ms

                if remaining > 0:
                    timeout = min(timeout, remaining)

        # Consider historical operation timeouts
        if operation in self.operation_timeouts:
            historical = self.operation_timeouts[operation]
            # Use P95 estimate (mean + 2*stddev approximation)
            suggested = historical * 1.5

            # Balance between requested and historical
            timeout = (timeout * 0.7) + (suggested * 0.3)

        return max(self.config.min_timeout_ms, timeout)

    async def _execute_function(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)

    def _record_event(
        self,
        operation: str,
        timeout_ms: float,
        actual_duration_ms: float | None,
        timed_out: bool,
        error: str | None = None,
    ):
        """Record timeout event.

        Args:
            operation: Operation name
            timeout_ms: Timeout used
            actual_duration_ms: Actual duration
            timed_out: Whether timeout occurred
            error: Error message if any
        """
        event = TimeoutEvent(
            timestamp=datetime.utcnow(),
            operation=operation,
            timeout_ms=timeout_ms,
            actual_duration_ms=actual_duration_ms,
            timed_out=timed_out,
            error=error,
        )

        self.timeout_events.append(event)

        # Keep only recent events
        if len(self.timeout_events) > 10000:
            self.timeout_events = self.timeout_events[-5000:]

    def _update_operation_timeout(self, operation: str, duration_ms: float):
        """Update operation timeout statistics.

        Args:
            operation: Operation name
            duration_ms: Actual duration
        """
        if operation not in self.operation_timeouts:
            self.operation_timeouts[operation] = duration_ms
        else:
            # Exponential moving average
            alpha = 0.1
            self.operation_timeouts[operation] = (1 - alpha) * self.operation_timeouts[
                operation
            ] + alpha * duration_ms

    def get_remaining_time(self) -> float | None:
        """Get remaining time from propagated deadline.

        Returns:
            Remaining time in milliseconds or None
        """
        deadline = deadline_context.get()
        if deadline:
            remaining = (deadline - time.time()) * 1000
            return max(0, remaining)
        return None

    def create_child_timeout(self, percentage: float = 0.9) -> float:
        """Create child timeout from current deadline.

        Args:
            percentage: Percentage of remaining time to use

        Returns:
            Child timeout in milliseconds
        """
        remaining = self.get_remaining_time()

        if remaining:
            child_timeout = remaining * percentage
            return max(self.config.min_timeout_ms, child_timeout)

        return self.config.default_timeout_ms

    def get_statistics(self) -> dict[str, Any]:
        """Get timeout statistics.

        Returns:
            Statistics dictionary
        """
        if not self.timeout_events:
            return {"total_operations": 0, "timeouts": 0, "timeout_rate": 0, "avg_duration_ms": 0}

        total = len(self.timeout_events)
        timeouts = sum(1 for e in self.timeout_events if e.timed_out)

        durations = [
            e.actual_duration_ms for e in self.timeout_events if e.actual_duration_ms is not None
        ]

        # Operation-specific stats
        operation_stats = {}
        for event in self.timeout_events:
            if event.operation not in operation_stats:
                operation_stats[event.operation] = {"total": 0, "timeouts": 0, "durations": []}

            operation_stats[event.operation]["total"] += 1
            if event.timed_out:
                operation_stats[event.operation]["timeouts"] += 1
            if event.actual_duration_ms:
                operation_stats[event.operation]["durations"].append(event.actual_duration_ms)

        # Calculate per-operation metrics
        for _op, stats in operation_stats.items():
            if stats["durations"]:
                stats["avg_duration_ms"] = sum(stats["durations"]) / len(stats["durations"])
                stats["max_duration_ms"] = max(stats["durations"])
                stats["min_duration_ms"] = min(stats["durations"])
            else:
                stats["avg_duration_ms"] = 0
                stats["max_duration_ms"] = 0
                stats["min_duration_ms"] = 0

            stats["timeout_rate"] = stats["timeouts"] / stats["total"] if stats["total"] > 0 else 0
            del stats["durations"]  # Remove raw data from output

        return {
            "total_operations": total,
            "timeouts": timeouts,
            "timeout_rate": timeouts / total if total > 0 else 0,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "min_duration_ms": min(durations) if durations else 0,
            "operation_stats": operation_stats,
            "suggested_timeouts": self.operation_timeouts,
        }


class CascadingTimeout:
    """Context manager for cascading timeouts."""

    def __init__(
        self,
        timeout_ms: float,
        operation: str = "cascading_operation",
        manager: TimeoutManager | None = None,
    ):
        """Initialize cascading timeout.

        Args:
            timeout_ms: Total timeout for operation
            operation: Operation name
            manager: Timeout manager instance
        """
        self.timeout_ms = timeout_ms
        self.operation = operation
        self.manager = manager or TimeoutManager()
        self.start_time = None
        self.deadline = None

    async def __aenter__(self):
        """Enter context."""
        self.start_time = time.time()
        self.deadline = self.start_time + (self.timeout_ms / 1000)

        # Set deadline in context
        deadline_context.set(self.deadline)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        # Clear deadline
        deadline_context.set(None)

        # Record execution
        if self.start_time:
            duration = (time.time() - self.start_time) * 1000
            timed_out = duration >= self.timeout_ms

            if self.manager:
                self.manager._record_event(
                    operation=self.operation,
                    timeout_ms=self.timeout_ms,
                    actual_duration_ms=duration,
                    timed_out=timed_out,
                    error=str(exc_val) if exc_val else None,
                )

    def get_remaining(self) -> float:
        """Get remaining time.

        Returns:
            Remaining time in milliseconds
        """
        if self.deadline:
            remaining = (self.deadline - time.time()) * 1000
            return max(0, remaining)
        return 0

    def create_child_timeout(self, percentage: float = 0.9, min_timeout_ms: float = 100) -> float:
        """Create child timeout.

        Args:
            percentage: Percentage of remaining time
            min_timeout_ms: Minimum timeout

        Returns:
            Child timeout in milliseconds
        """
        remaining = self.get_remaining()
        child_timeout = remaining * percentage
        return max(min_timeout_ms, child_timeout)


class TimeoutException(Exception):
    """Exception raised when operation times out."""

    pass


# Decorator for timeout functionality
def timeout(
    timeout_ms: float, operation: str = "decorated_operation", propagate_deadline: bool = True
):
    """Decorator for adding timeout to functions.

    Args:
        timeout_ms: Timeout in milliseconds
        operation: Operation name
        propagate_deadline: Whether to propagate deadline
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            manager = TimeoutManager()
            # Remove propagate_deadline from kwargs if present to avoid duplicate
            propagate = kwargs.pop('propagate_deadline', propagate_deadline)
            return await manager.execute_with_timeout(
                func,
                *args,
                timeout_ms=timeout_ms,
                operation=operation,
                propagate_deadline=propagate,
                **kwargs,
            )

        return wrapper

    return decorator

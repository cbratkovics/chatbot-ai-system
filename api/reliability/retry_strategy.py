"""Retry strategies with exponential backoff and jitter."""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""

    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    FIBONACCI_BACKOFF = "fibonacci_backoff"
    ADAPTIVE = "adaptive"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_delay_ms: float = 1000
    max_delay_ms: float = 30000
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1
    retryable_exceptions: set[type[Exception]] = None
    non_retryable_exceptions: set[type[Exception]] = None
    retry_on_timeout: bool = True

    def __post_init__(self):
        if self.retryable_exceptions is None:
            self.retryable_exceptions = {Exception}
        if self.non_retryable_exceptions is None:
            self.non_retryable_exceptions = set()


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""

    attempt_number: int
    delay_ms: float
    exception: Exception | None
    timestamp: float
    succeeded: bool


class RetryExecutor:
    """Executes functions with retry logic."""

    def __init__(
        self,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        config: RetryConfig | None = None,
    ):
        """Initialize retry executor.

        Args:
            strategy: Retry strategy to use
            config: Retry configuration
        """
        self.strategy = strategy
        self.config = config or RetryConfig()
        self.attempt_history: list[RetryAttempt] = []
        self.fibonacci_cache = [0, 1]

    async def execute(
        self, func: Callable, *args, on_retry: Callable | None = None, **kwargs
    ) -> Any:
        """Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Function arguments
            on_retry: Callback on retry attempt
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        attempt = 0
        last_exception = None

        while attempt < self.config.max_attempts:
            attempt += 1

            # Calculate delay for this attempt
            delay_ms = self._calculate_delay(attempt)

            # Wait before retry (except first attempt)
            if attempt > 1:
                if on_retry:
                    await on_retry(attempt - 1, delay_ms, last_exception)

                await asyncio.sleep(delay_ms / 1000)

            # Execute function
            start_time = time.time()

            try:
                result = await self._execute_function(func, *args, **kwargs)

                # Record successful attempt
                self.attempt_history.append(
                    RetryAttempt(
                        attempt_number=attempt,
                        delay_ms=delay_ms if attempt > 1 else 0,
                        exception=None,
                        timestamp=start_time,
                        succeeded=True,
                    )
                )

                return result

            except Exception as e:
                last_exception = e

                # Record failed attempt
                self.attempt_history.append(
                    RetryAttempt(
                        attempt_number=attempt,
                        delay_ms=delay_ms if attempt > 1 else 0,
                        exception=e,
                        timestamp=start_time,
                        succeeded=False,
                    )
                )

                # Check if should retry
                if not self._should_retry(e, attempt):
                    raise

                logger.warning(f"Attempt {attempt} failed: {e}. " f"Retrying in {delay_ms}ms...")

        # Max attempts reached
        raise MaxRetriesExceededException(f"Failed after {attempt} attempts", last_exception)

    async def _execute_function(self, func: Callable, *args, **kwargs) -> Any:
        """Execute the function.

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

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for attempt.

        Args:
            attempt: Attempt number (1-based)

        Returns:
            Delay in milliseconds
        """
        if attempt == 1:
            return 0  # No delay for first attempt

        if self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self._exponential_backoff(attempt)
        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self._linear_backoff(attempt)
        elif self.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.initial_delay_ms
        elif self.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            delay = self._fibonacci_backoff(attempt)
        elif self.strategy == RetryStrategy.ADAPTIVE:
            delay = self._adaptive_backoff(attempt)
        else:
            delay = self.config.initial_delay_ms

        # Apply maximum delay cap
        delay = min(delay, self.config.max_delay_ms)

        # Apply jitter
        if self.config.jitter:
            delay = self._apply_jitter(delay)

        return delay

    def _exponential_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay.

        Args:
            attempt: Attempt number

        Returns:
            Delay in milliseconds
        """
        return self.config.initial_delay_ms * (self.config.backoff_multiplier ** (attempt - 2))

    def _linear_backoff(self, attempt: int) -> float:
        """Calculate linear backoff delay.

        Args:
            attempt: Attempt number

        Returns:
            Delay in milliseconds
        """
        return self.config.initial_delay_ms * (attempt - 1)

    def _fibonacci_backoff(self, attempt: int) -> float:
        """Calculate Fibonacci backoff delay.

        Args:
            attempt: Attempt number

        Returns:
            Delay in milliseconds
        """
        # Build Fibonacci sequence if needed
        while len(self.fibonacci_cache) < attempt:
            self.fibonacci_cache.append(self.fibonacci_cache[-1] + self.fibonacci_cache[-2])

        return self.config.initial_delay_ms * self.fibonacci_cache[attempt - 1]

    def _adaptive_backoff(self, attempt: int) -> float:
        """Calculate adaptive backoff based on history.

        Args:
            attempt: Attempt number

        Returns:
            Delay in milliseconds
        """
        # Start with exponential backoff
        base_delay = self._exponential_backoff(attempt)

        # Adjust based on recent success rate
        if len(self.attempt_history) >= 10:
            recent = self.attempt_history[-10:]
            success_rate = sum(1 for a in recent if a.succeeded) / len(recent)

            if success_rate < 0.2:  # Very low success rate
                # Increase delay
                base_delay *= 1.5
            elif success_rate > 0.8:  # High success rate
                # Decrease delay
                base_delay *= 0.7

        return base_delay

    def _apply_jitter(self, delay: float) -> float:
        """Apply jitter to delay.

        Args:
            delay: Base delay in milliseconds

        Returns:
            Delay with jitter
        """
        jitter_amount = delay * self.config.jitter_factor
        jitter = random.uniform(-jitter_amount, jitter_amount)
        return max(0, delay + jitter)

    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """Check if should retry after exception.

        Args:
            exception: Exception that occurred
            attempt: Current attempt number

        Returns:
            True if should retry
        """
        # Check if max attempts reached
        if attempt >= self.config.max_attempts:
            return False

        # Check non-retryable exceptions
        for exc_type in self.config.non_retryable_exceptions:
            if isinstance(exception, exc_type):
                return False

        # Check retryable exceptions
        for exc_type in self.config.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True

        # Check timeout specifically
        if isinstance(exception, asyncio.TimeoutError):
            return self.config.retry_on_timeout

        # Default to not retry
        return False

    def get_statistics(self) -> dict[str, Any]:
        """Get retry statistics.

        Returns:
            Statistics dictionary
        """
        if not self.attempt_history:
            return {
                "total_attempts": 0,
                "successful_attempts": 0,
                "failed_attempts": 0,
                "success_rate": 0,
                "avg_delay_ms": 0,
            }

        successful = sum(1 for a in self.attempt_history if a.succeeded)
        failed = len(self.attempt_history) - successful
        delays = [a.delay_ms for a in self.attempt_history if a.delay_ms > 0]

        return {
            "total_attempts": len(self.attempt_history),
            "successful_attempts": successful,
            "failed_attempts": failed,
            "success_rate": successful / len(self.attempt_history),
            "avg_delay_ms": sum(delays) / len(delays) if delays else 0,
            "max_delay_ms": max(delays) if delays else 0,
            "strategy": self.strategy.value,
        }

    def reset_history(self):
        """Reset attempt history."""
        self.attempt_history.clear()


class BulkheadRetryExecutor:
    """Retry executor with bulkhead isolation."""

    def __init__(
        self,
        max_concurrent: int = 10,
        queue_size: int = 100,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        config: RetryConfig | None = None,
    ):
        """Initialize bulkhead retry executor.

        Args:
            max_concurrent: Maximum concurrent executions
            queue_size: Maximum queue size
            strategy: Retry strategy
            config: Retry configuration
        """
        self.max_concurrent = max_concurrent
        self.queue_size = queue_size
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self.retry_executor = RetryExecutor(strategy, config)
        self.active_executions = 0

    async def execute(self, func: Callable, *args, priority: int = 0, **kwargs) -> Any:
        """Execute function with bulkhead isolation and retry.

        Args:
            func: Function to execute
            *args: Function arguments
            priority: Execution priority (higher = higher priority)
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        # Check queue size
        if self.queue.qsize() >= self.queue_size:
            raise BulkheadRejectedException("Queue is full")

        # Add to queue with priority
        await self.queue.put((priority, func, args, kwargs))

        # Process queue
        return await self._process_queue()

    async def _process_queue(self) -> Any:
        """Process execution queue.

        Returns:
            Execution result
        """
        # Get highest priority item
        priority, func, args, kwargs = await self.queue.get()

        # Acquire semaphore for execution
        async with self.semaphore:
            self.active_executions += 1

            try:
                # Execute with retry
                result = await self.retry_executor.execute(func, *args, **kwargs)
                return result

            finally:
                self.active_executions -= 1

    def get_status(self) -> dict[str, Any]:
        """Get bulkhead status.

        Returns:
            Status dictionary
        """
        return {
            "active_executions": self.active_executions,
            "max_concurrent": self.max_concurrent,
            "queue_size": self.queue.qsize(),
            "max_queue_size": self.queue_size,
            "available_slots": self.max_concurrent - self.active_executions,
        }


class MaxRetriesExceededException(Exception):
    """Exception raised when max retries exceeded."""

    def __init__(self, message: str, last_exception: Exception | None = None):
        super().__init__(message)
        self.last_exception = last_exception


class BulkheadRejectedException(Exception):
    """Exception raised when bulkhead rejects execution."""

    pass


# Decorator for retry functionality
def retry(
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    max_attempts: int = 3,
    initial_delay_ms: float = 1000,
    **config_kwargs,
):
    """Decorator for adding retry logic to functions.

    Args:
        strategy: Retry strategy
        max_attempts: Maximum retry attempts
        initial_delay_ms: Initial delay in milliseconds
        **config_kwargs: Additional configuration parameters
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts, initial_delay_ms=initial_delay_ms, **config_kwargs
            )
            executor = RetryExecutor(strategy, config)
            return await executor.execute(func, *args, **kwargs)

        return wrapper

    return decorator

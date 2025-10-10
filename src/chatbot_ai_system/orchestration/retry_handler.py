"""Retry handler with exponential backoff."""

import asyncio
from collections.abc import Callable
from typing import TypeVar

from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
)

T = TypeVar("T")


class RetryHandler:
    """Intelligent retry handler with exponential backoff."""

    def __init__(
        self,
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 30.0,
        multiplier: float = 2.0,
        jitter: bool = True,
    ):
        """Initialize retry handler."""
        self.max_attempts = max_attempts
        self.min_wait = min_wait
        self.max_wait = max_wait
        self.multiplier = multiplier
        self.jitter = jitter

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        on_retry: Callable[[Exception, int], None] | None = None,
        **kwargs,
    ) -> T:
        """Execute function with retry logic."""
        wait_strategy = (
            wait_random_exponential(
                multiplier=self.multiplier,
                min=self.min_wait,
                max=self.max_wait,
            )
            if self.jitter
            else wait_exponential(
                multiplier=self.multiplier,
                min=self.min_wait,
                max=self.max_wait,
            )
        )

        attempt = 0

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.max_attempts),
                wait=wait_strategy,
                reraise=True,
            ):
                with attempt:
                    try:
                        if asyncio.iscoroutinefunction(func):
                            return await func(*args, **kwargs)
                        else:
                            return func(*args, **kwargs)
                    except Exception as e:
                        if on_retry and attempt.retry_state.attempt_number < self.max_attempts:
                            on_retry(e, attempt.retry_state.attempt_number)
                        raise
        except RetryError as e:
            raise e.last_attempt.exception() from None
        
        # This should never be reached
        raise RuntimeError("Retry loop completed without returning")

    @staticmethod
    def with_exponential_backoff(
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ) -> "RetryHandler":
        """Create retry handler with exponential backoff."""
        return RetryHandler(
            max_attempts=max_attempts,
            min_wait=base_delay,
            max_wait=max_delay,
            multiplier=2.0,
            jitter=True,
        )

    @staticmethod
    def with_linear_backoff(
        max_attempts: int = 3,
        delay: float = 1.0,
    ) -> "RetryHandler":
        """Create retry handler with linear backoff."""
        return RetryHandler(
            max_attempts=max_attempts,
            min_wait=delay,
            max_wait=delay,
            multiplier=1.0,
            jitter=False,
        )

"""Rate limiting functionality."""

from typing import Any, Dict, List, Tuple, Optional
import asyncio
import time


class TokenBucket:
    """Token bucket rate limiter implementation."""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize the token bucket.

        Args:
            capacity: Maximum number of tokens in the bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False otherwise
        """
        async with self._lock:
            self._refill()

            if tokens > self.capacity:
                return False

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False

    def _refill(self):
        """Refill the bucket based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate

        self.tokens = min(float(self.capacity), self.tokens + tokens_to_add)
        self.last_refill = now

    async def wait_for_tokens(self, tokens: int = 1, timeout: float | None = None) -> bool:
        """
        Wait for tokens to become available.

        Args:
            tokens: Number of tokens needed
            timeout: Maximum time to wait in seconds

        Returns:
            True if tokens were consumed, False if timeout occurred
        """
        start_time = time.time()

        while True:
            if await self.consume(tokens):
                return True

            if timeout and (time.time() - start_time) >= timeout:
                return False

            await asyncio.sleep(0.1)

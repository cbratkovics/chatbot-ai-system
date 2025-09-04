"""Test rate limiting functionality."""
import time
import pytest
from unittest.mock import MagicMock, patch

# Create a simple TokenBucket class for testing
class TokenBucket:
    """Token bucket for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """Consume tokens from the bucket."""
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate

        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

class TestTokenBucket:
    """Test token bucket rate limiter."""

    def test_token_bucket_creation(self):
        """Test creating a token bucket."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        assert bucket.capacity == 10
        assert bucket.refill_rate == 1.0
        assert bucket.tokens == 10

    def test_consume_tokens(self):
        """Test consuming tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        # Should succeed
        assert bucket.consume(5) is True
        assert bucket.tokens <= 5

        # Should succeed
        assert bucket.consume(3) is True

        # Should fail
        assert bucket.consume(5) is False

    def test_consume_exceeds_capacity(self):
        """Test consuming more tokens than capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        # Should fail
        assert bucket.consume(15) is False
        assert bucket.tokens == 10

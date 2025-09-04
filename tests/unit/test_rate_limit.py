"""Test rate limiting functionality."""

import json
import time
from unittest.mock import AsyncMock, Mock

import pytest

from chatbot_ai_system.server.middleware.rate_limiter import TokenBucket


class TestTokenBucket:
    def test_token_bucket_creation(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=10, last_refill=time.time())
        assert bucket.capacity == 10
        assert bucket.tokens == 10

    def test_consume_tokens(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=10, last_refill=time.time())
        assert bucket.consume(5) is True
        assert bucket.tokens == 5

    def test_consume_exceeds_capacity(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0, tokens=10, last_refill=time.time())
        assert bucket.consume(15) is False
        assert bucket.tokens == 10

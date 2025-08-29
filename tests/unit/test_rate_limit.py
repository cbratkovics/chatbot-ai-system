"""Test rate limiting functionality."""

import json
from unittest.mock import AsyncMock, Mock

import pytest

from chatbot_system_core import TokenBucket


class TestTokenBucket:
    def test_token_bucket_creation(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.capacity == 10
        assert bucket.tokens == 10

    @pytest.mark.asyncio
    async def test_consume_tokens(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert await bucket.consume(5) is True
        assert bucket.tokens == 5

    @pytest.mark.asyncio
    async def test_consume_exceeds_capacity(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert await bucket.consume(15) is False
        assert bucket.tokens == 10

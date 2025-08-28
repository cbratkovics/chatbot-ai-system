"""Unit tests for rate limiter."""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


class TestRateLimiter:
    """Test suite for rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_token_bucket_initialization(self, mock_redis):
        """Test token bucket rate limiter initialization."""
        from api.core.tenancy.rate_limiter import TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter(redis_client=mock_redis, capacity=100, refill_rate=10)

        assert limiter.capacity == 100
        assert limiter.refill_rate == 10
        assert limiter.redis_client == mock_redis

    @pytest.mark.asyncio
    async def test_token_consumption(self, mock_redis):
        """Test token consumption."""
        from api.core.tenancy.rate_limiter import TokenBucketRateLimiter

        mock_redis.hget.return_value = "100"
        mock_redis.hset.return_value = 1

        limiter = TokenBucketRateLimiter(redis_client=mock_redis, capacity=100, refill_rate=10)

        allowed = await limiter.allow_request("user123", tokens=10)
        assert allowed is True

        mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, mock_redis):
        """Test rate limit exceeded scenario."""
        from api.core.tenancy.rate_limiter import TokenBucketRateLimiter

        mock_redis.hget.return_value = "5"

        limiter = TokenBucketRateLimiter(redis_client=mock_redis, capacity=100, refill_rate=10)

        allowed = await limiter.allow_request("user123", tokens=10)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_token_refill(self, mock_redis):
        """Test token refill mechanism."""
        from api.core.tenancy.rate_limiter import TokenBucketRateLimiter

        initial_time = datetime.utcnow()
        mock_redis.hget.side_effect = ["50", initial_time.isoformat()]

        limiter = TokenBucketRateLimiter(redis_client=mock_redis, capacity=100, refill_rate=10)

        with patch("api.core.tenancy.rate_limiter.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = initial_time + timedelta(seconds=5)

            tokens = await limiter.get_available_tokens("user123")
            assert tokens == 100

    @pytest.mark.asyncio
    async def test_sliding_window_limiter(self, mock_redis):
        """Test sliding window rate limiter."""
        from api.core.tenancy.rate_limiter import SlidingWindowRateLimiter

        limiter = SlidingWindowRateLimiter(
            redis_client=mock_redis, window_seconds=60, max_requests=100
        )

        mock_redis.zcount.return_value = 50

        allowed = await limiter.allow_request("user123")
        assert allowed is True

        mock_redis.zadd.assert_called()

    @pytest.mark.asyncio
    async def test_distributed_rate_limiting(self, mock_redis):
        """Test distributed rate limiting across multiple instances."""
        from api.core.tenancy.rate_limiter import DistributedRateLimiter

        limiter = DistributedRateLimiter(
            redis_client=mock_redis, max_requests=100, window_seconds=60
        )

        mock_redis.eval.return_value = 1

        allowed = await limiter.allow_request("user123")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_tenant_specific_limits(self, mock_redis, tenant_config):
        """Test tenant-specific rate limits."""
        from api.core.tenancy.rate_limiter import TenantRateLimiter

        limiter = TenantRateLimiter(redis_client=mock_redis)

        mock_redis.hget.return_value = json.dumps(tenant_config["rate_limits"])

        limits = await limiter.get_tenant_limits(tenant_config["tenant_id"])
        assert limits["requests_per_minute"] == 1000

    @pytest.mark.asyncio
    async def test_burst_allowance(self, mock_redis):
        """Test burst traffic allowance."""
        from api.core.tenancy.rate_limiter import TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter(
            redis_client=mock_redis, capacity=100, refill_rate=10, burst_size=20
        )

        mock_redis.hget.return_value = "100"

        allowed = await limiter.allow_burst("user123", tokens=120)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, mock_redis):
        """Test rate limit header generation."""
        from api.core.tenancy.rate_limiter import RateLimiter

        limiter = RateLimiter(redis_client=mock_redis)

        headers = await limiter.get_rate_limit_headers(
            key="user123",
            limit=100,
            remaining=75,
            reset_time=datetime.utcnow() + timedelta(seconds=30),
        )

        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "75"
        assert "X-RateLimit-Reset" in headers

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, mock_redis):
        """Test handling of concurrent requests."""
        from api.core.tenancy.rate_limiter import TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter(redis_client=mock_redis, capacity=100, refill_rate=10)

        mock_redis.hget.return_value = "100"

        tasks = []
        for _ in range(10):
            task = limiter.allow_request("user123", tokens=1)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        assert all(results)

    @pytest.mark.asyncio
    async def test_rate_limit_bypass(self, mock_redis):
        """Test rate limit bypass for privileged users."""
        from api.core.tenancy.rate_limiter import RateLimiter

        limiter = RateLimiter(redis_client=mock_redis, bypass_keys=["admin", "service"])

        allowed = await limiter.allow_request("admin", bypass=True)
        assert allowed is True
        mock_redis.hget.assert_not_called()

    @pytest.mark.asyncio
    async def test_adaptive_rate_limiting(self, mock_redis):
        """Test adaptive rate limiting based on system load."""
        from api.core.tenancy.rate_limiter import AdaptiveRateLimiter

        limiter = AdaptiveRateLimiter(redis_client=mock_redis)

        with patch("api.core.tenancy.rate_limiter.get_system_load") as mock_load:
            mock_load.return_value = 0.8

            adjusted_limit = await limiter.get_adjusted_limit(base_limit=100)
            assert adjusted_limit < 100

    @pytest.mark.asyncio
    async def test_rate_limit_metrics(self, mock_redis, mock_metrics_collector):
        """Test rate limit metrics collection."""
        from api.core.tenancy.rate_limiter import RateLimiter

        limiter = RateLimiter(redis_client=mock_redis, metrics_collector=mock_metrics_collector)

        await limiter.allow_request("user123")

        mock_metrics_collector.increment_counter.assert_called()

    @pytest.mark.asyncio
    async def test_grace_period(self, mock_redis):
        """Test grace period for rate limit violations."""
        from api.core.tenancy.rate_limiter import RateLimiter

        limiter = RateLimiter(redis_client=mock_redis, grace_period_seconds=5)

        mock_redis.hget.return_value = "0"

        allowed = await limiter.allow_request_with_grace("user123")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_quota_reset(self, mock_redis):
        """Test quota reset functionality."""
        from api.core.tenancy.rate_limiter import RateLimiter

        limiter = RateLimiter(redis_client=mock_redis)

        await limiter.reset_quota("user123")

        mock_redis.delete.assert_called_with("rate_limit:user123")

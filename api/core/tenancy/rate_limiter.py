"""Rate limiter implementations with token bucket and sliding window."""

import json
import logging
import time
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RateLimiter:
    """Base rate limiter class."""

    def __init__(
        self,
        redis_client: aioredis.Redis,
        window_seconds: int = 60,
        max_requests: int = 100,
        bypass_keys: set[str] | None = None,
        grace_period_seconds: int = 0,
        metrics_collector: Any | None = None,
    ):
        """Initialize rate limiter.

        Args:
            redis_client: Redis client
            window_seconds: Time window in seconds
            max_requests: Maximum requests in window
            bypass_keys: Keys to bypass rate limiting
            grace_period_seconds: Grace period for violations
            metrics_collector: Metrics collector
        """
        self.redis_client = redis_client
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.bypass_keys = bypass_keys or set()
        self.grace_period_seconds = grace_period_seconds
        self.metrics_collector = metrics_collector

    async def allow_request(self, key: str, bypass: bool = False) -> bool:
        """Check if request is allowed.

        Args:
            key: Rate limit key
            bypass: Bypass rate limiting

        Returns:
            True if allowed
        """
        if bypass or key in self.bypass_keys:
            return True

        current_count = await self._get_current_count(key)

        if current_count >= self.max_requests:
            if self.metrics_collector:
                self.metrics_collector.increment_counter("rate_limit_exceeded")
            return False

        await self._increment_count(key)

        if self.metrics_collector:
            self.metrics_collector.increment_counter("rate_limit_allowed")

        return True

    async def allow_request_with_grace(self, key: str) -> bool:
        """Check if request is allowed with grace period.

        Args:
            key: Rate limit key

        Returns:
            True if allowed
        """
        current_count = await self._get_current_count(key)

        if current_count == 0 and self.grace_period_seconds > 0:
            return True

        return await self.allow_request(key)

    async def _get_current_count(self, key: str) -> int:
        """Get current request count.

        Args:
            key: Rate limit key

        Returns:
            Current count
        """
        count = await self.redis_client.get(f"rate_limit:{key}")
        if not count:
            return 0
        try:
            # Handle bytes
            if isinstance(count, bytes):
                count = count.decode()
            # Try to parse as int first
            if '.' not in str(count):
                return int(count)
            # If it's a float timestamp, that means no count
            return 0
        except (ValueError, TypeError):
            return 0

    async def _increment_count(self, key: str):
        """Increment request count.

        Args:
            key: Rate limit key
        """
        redis_key = f"rate_limit:{key}"
        await self.redis_client.incr(redis_key)
        await self.redis_client.expire(redis_key, self.window_seconds)

    async def get_rate_limit_headers(
        self, key: str, limit: int, remaining: int, reset_time: datetime
    ) -> dict[str, str]:
        """Get rate limit headers.

        Args:
            key: Rate limit key
            limit: Rate limit
            remaining: Remaining requests
            reset_time: Reset time

        Returns:
            Rate limit headers
        """
        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(reset_time.timestamp())),
        }

    async def reset_quota(self, key: str):
        """Reset quota for key.

        Args:
            key: Rate limit key
        """
        await self.redis_client.delete(f"rate_limit:{key}")


class TokenBucketRateLimiter(RateLimiter):
    """Token bucket rate limiter implementation."""

    def __init__(
        self,
        redis_client: aioredis.Redis,
        capacity: int = 100,
        refill_rate: float = 10.0,
        burst_size: int = 0,
        **kwargs,
    ):
        """Initialize token bucket rate limiter.

        Args:
            redis_client: Redis client
            capacity: Bucket capacity
            refill_rate: Tokens per second
            burst_size: Additional burst capacity
            **kwargs: Additional arguments
        """
        super().__init__(redis_client, **kwargs)
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.burst_size = burst_size

    async def allow_request(self, key: str, tokens: int = 1) -> bool:
        """Check if request is allowed.

        Args:
            key: Rate limit key
            tokens: Tokens required

        Returns:
            True if allowed
        """
        bucket_key = f"token_bucket:{key}"

        tokens_str = await self.redis_client.hget(bucket_key, "tokens")
        last_refill_str = await self.redis_client.hget(bucket_key, "last_refill")

        current_time = time.time()

        if tokens_str is None:
            tokens_available = self.capacity
            last_refill = current_time
        else:
            tokens_available = float(tokens_str)
            try:
                last_refill = float(last_refill_str) if last_refill_str else current_time
            except (ValueError, TypeError):
                # Handle ISO format timestamps
                from datetime import datetime
                if last_refill_str and 'T' in str(last_refill_str):
                    dt = datetime.fromisoformat(str(last_refill_str))
                    last_refill = dt.timestamp()
                else:
                    last_refill = current_time

            time_passed = current_time - last_refill
            tokens_to_add = time_passed * self.refill_rate
            tokens_available = min(self.capacity, tokens_available + tokens_to_add)

        if tokens_available >= tokens:
            tokens_available -= tokens

            await self.redis_client.hset(bucket_key, "tokens", str(tokens_available))
            await self.redis_client.hset(bucket_key, "last_refill", str(current_time))
            await self.redis_client.expire(bucket_key, 3600)

            return True

        return False

    async def allow_burst(self, key: str, tokens: int) -> bool:
        """Allow burst traffic.

        Args:
            key: Rate limit key
            tokens: Tokens required

        Returns:
            True if allowed
        """
        if tokens <= self.capacity + self.burst_size:
            return await self.allow_request(key, tokens)
        return False

    async def get_available_tokens(self, key: str) -> float:
        """Get available tokens.

        Args:
            key: Rate limit key

        Returns:
            Available tokens
        """
        bucket_key = f"token_bucket:{key}"

        tokens_str = await self.redis_client.hget(bucket_key, "tokens")
        last_refill_str = await self.redis_client.hget(bucket_key, "last_refill")

        if tokens_str is None:
            return self.capacity

        current_time = time.time()
        tokens_available = float(tokens_str)
        try:
            last_refill = float(last_refill_str) if last_refill_str else current_time
        except (ValueError, TypeError):
            # Handle ISO format timestamps
            from datetime import datetime
            if last_refill_str and 'T' in str(last_refill_str):
                dt = datetime.fromisoformat(str(last_refill_str))
                last_refill = dt.timestamp()
            else:
                last_refill = current_time

        time_passed = current_time - last_refill
        tokens_to_add = time_passed * self.refill_rate

        return min(self.capacity, tokens_available + tokens_to_add)


class SlidingWindowRateLimiter(RateLimiter):
    """Sliding window rate limiter implementation."""

    async def allow_request(self, key: str) -> bool:
        """Check if request is allowed.

        Args:
            key: Rate limit key

        Returns:
            True if allowed
        """
        window_key = f"sliding_window:{key}"
        current_time = time.time()
        window_start = current_time - self.window_seconds

        await self.redis_client.zremrangebyscore(window_key, 0, window_start)

        request_count = await self.redis_client.zcount(window_key, window_start, current_time)

        if request_count >= self.max_requests:
            return False

        await self.redis_client.zadd(window_key, {str(current_time): current_time})
        await self.redis_client.expire(window_key, self.window_seconds + 1)

        return True


class DistributedRateLimiter(RateLimiter):
    """Distributed rate limiter using Lua script."""

    def __init__(self, *args, **kwargs):
        """Initialize distributed rate limiter."""
        super().__init__(*args, **kwargs)

        self.lua_script = """
        local key = KEYS[1]
        local limit = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local current = redis.call('INCR', key)
        
        if current == 1 then
            redis.call('EXPIRE', key, window)
        end
        
        if current > limit then
            return 0
        else
            return 1
        end
        """

    async def allow_request(self, key: str) -> bool:
        """Check if request is allowed.

        Args:
            key: Rate limit key

        Returns:
            True if allowed
        """
        result = await self.redis_client.eval(
            self.lua_script, 1, f"distributed:{key}", self.max_requests, self.window_seconds
        )

        return result == 1


class TenantRateLimiter(TokenBucketRateLimiter):
    """Tenant-specific rate limiter."""

    async def get_tenant_limits(self, tenant_id: str) -> dict[str, Any]:
        """Get tenant-specific limits.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Tenant limits
        """
        limits_key = f"tenant_limits:{tenant_id}"
        limits_str = await self.redis_client.hget(limits_key, "limits")

        if limits_str:
            return json.loads(limits_str)

        return {"requests_per_minute": 100, "tokens_per_day": 100000, "concurrent_connections": 10}

    async def allow_request_for_tenant(self, tenant_id: str, resource: str = "api_calls") -> bool:
        """Check if request is allowed for tenant.

        Args:
            tenant_id: Tenant identifier
            resource: Resource type

        Returns:
            True if allowed
        """
        limits = await self.get_tenant_limits(tenant_id)

        if resource == "api_calls":
            self.max_requests = limits.get("requests_per_minute", 100)
            self.window_seconds = 60
        elif resource == "tokens":
            self.max_requests = limits.get("tokens_per_day", 100000)
            self.window_seconds = 86400

        return await self.allow_request(f"{tenant_id}:{resource}")


class AdaptiveRateLimiter(TokenBucketRateLimiter):
    """Adaptive rate limiter based on system load."""

    async def get_adjusted_limit(self, base_limit: int) -> int:
        """Get adjusted limit based on system load.

        Args:
            base_limit: Base rate limit

        Returns:
            Adjusted limit
        """
        system_load = await self._get_system_load()

        if system_load > 0.8:
            return int(base_limit * 0.5)
        elif system_load > 0.6:
            return int(base_limit * 0.75)
        else:
            return base_limit

    async def _get_system_load(self) -> float:
        """Get current system load.

        Returns:
            System load (0-1)
        """
        try:
            import psutil

            return psutil.cpu_percent() / 100.0
        except ImportError:
            return 0.5

    async def allow_request(self, key: str, tokens: int = 1) -> bool:
        """Check if request is allowed with adaptive limits.

        Args:
            key: Rate limit key
            tokens: Tokens required

        Returns:
            True if allowed
        """
        self.capacity = await self.get_adjusted_limit(self.capacity)
        return await super().allow_request(key, tokens)

def get_system_load() -> float:
    """Get current system load for adaptive rate limiting."""
    import psutil
    try:
        return psutil.cpu_percent(interval=0.1) / 100.0
    except:
        return 0.5  # Default to 50% if unable to determine

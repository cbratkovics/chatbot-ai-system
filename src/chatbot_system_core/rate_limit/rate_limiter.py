"""Token bucket rate limiter for per-tenant rate limiting."""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: int
    refill_rate: float
    tokens: float
    last_refill: float

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        self.refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def refill(self):
        """Refill bucket based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Calculate tokens to add
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now


class TenantRateLimiter:
    """Per-tenant rate limiter using token bucket algorithm."""

    def __init__(self):
        self.buckets: dict[str, dict[str, TokenBucket]] = {}
        self.lock = asyncio.Lock()

    async def check_rate_limit(
        self, tenant_id: str, resource: str, tokens: int = 1, tier: str = "basic"
    ) -> tuple[bool, dict[str, any]]:
        """Check if request is within rate limits.

        Args:
            tenant_id: Tenant identifier
            resource: Resource being accessed
            tokens: Number of tokens to consume
            tier: Tenant tier for limits

        Returns:
            Tuple of (allowed, metadata)
        """
        async with self.lock:
            # Get or create bucket for tenant/resource
            bucket = self._get_or_create_bucket(tenant_id, resource, tier)

            # Try to consume tokens
            allowed = bucket.consume(tokens)

            # Calculate wait time if rate limited
            wait_time = 0
            if not allowed:
                tokens_needed = tokens - bucket.tokens
                wait_time = tokens_needed / bucket.refill_rate

            metadata = {
                "tokens_remaining": int(bucket.tokens),
                "capacity": bucket.capacity,
                "refill_rate": bucket.refill_rate,
                "wait_time_seconds": wait_time,
                "retry_after": datetime.utcnow() + timedelta(seconds=wait_time)
                if wait_time > 0
                else None,
            }

            return allowed, metadata

    def _get_or_create_bucket(self, tenant_id: str, resource: str, tier: str) -> TokenBucket:
        """Get or create token bucket for tenant/resource.

        Args:
            tenant_id: Tenant identifier
            resource: Resource type
            tier: Tenant tier

        Returns:
            Token bucket instance
        """
        if tenant_id not in self.buckets:
            self.buckets[tenant_id] = {}

        if resource not in self.buckets[tenant_id]:
            limits = self._get_resource_limits(resource, tier)
            self.buckets[tenant_id][resource] = TokenBucket(
                capacity=limits["capacity"],
                refill_rate=limits["refill_rate"],
                tokens=limits["capacity"],  # Start with full bucket
                last_refill=time.time(),
            )

        return self.buckets[tenant_id][resource]

    def _get_resource_limits(self, resource: str, tier: str) -> dict[str, float]:
        """Get rate limits for resource and tier.

        Args:
            resource: Resource type
            tier: Tenant tier

        Returns:
            Rate limit configuration
        """
        # Define limits per resource and tier
        limits = {
            "api_requests": {
                "basic": {"capacity": 100, "refill_rate": 1.67},  # 100 req/min
                "professional": {"capacity": 300, "refill_rate": 5.0},  # 300 req/min
                "enterprise": {"capacity": 1000, "refill_rate": 16.67},  # 1000 req/min
            },
            "tokens": {
                "basic": {"capacity": 10000, "refill_rate": 166.67},  # 10k tokens/min
                "professional": {"capacity": 50000, "refill_rate": 833.33},  # 50k tokens/min
                "enterprise": {"capacity": 200000, "refill_rate": 3333.33},  # 200k tokens/min
            },
            "websocket_messages": {
                "basic": {"capacity": 60, "refill_rate": 1.0},  # 60 msg/min
                "professional": {"capacity": 180, "refill_rate": 3.0},  # 180 msg/min
                "enterprise": {"capacity": 600, "refill_rate": 10.0},  # 600 msg/min
            },
            "file_uploads": {
                "basic": {"capacity": 10, "refill_rate": 0.167},  # 10 per hour
                "professional": {"capacity": 50, "refill_rate": 0.833},  # 50 per hour
                "enterprise": {"capacity": 200, "refill_rate": 3.33},  # 200 per hour
            },
        }

        resource_limits = limits.get(resource, limits["api_requests"])
        return resource_limits.get(tier, resource_limits["basic"])

    async def reset_tenant_limits(self, tenant_id: str):
        """Reset all limits for a tenant.

        Args:
            tenant_id: Tenant identifier
        """
        async with self.lock:
            if tenant_id in self.buckets:
                del self.buckets[tenant_id]
                logger.info(f"Reset rate limits for tenant: {tenant_id}")

    async def get_tenant_status(self, tenant_id: str) -> dict[str, dict[str, any]]:
        """Get current rate limit status for tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Status for all resources
        """
        status = {}

        async with self.lock:
            if tenant_id in self.buckets:
                for resource, bucket in self.buckets[tenant_id].items():
                    bucket.refill()  # Ensure current state
                    status[resource] = {
                        "tokens_available": int(bucket.tokens),
                        "capacity": bucket.capacity,
                        "refill_rate": bucket.refill_rate,
                        "percent_available": (bucket.tokens / bucket.capacity) * 100,
                    }

        return status


class DistributedRateLimiter:
    """Distributed rate limiter using Redis for multi-instance coordination."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def check_rate_limit(
        self,
        tenant_id: str,
        resource: str,
        tokens: int = 1,
        window_seconds: int = 60,
        max_tokens: int = 100,
    ) -> tuple[bool, dict[str, any]]:
        """Check rate limit using sliding window in Redis.

        Args:
            tenant_id: Tenant identifier
            resource: Resource being accessed
            tokens: Tokens to consume
            window_seconds: Time window in seconds
            max_tokens: Maximum tokens in window

        Returns:
            Tuple of (allowed, metadata)
        """
        key = f"rate_limit:{tenant_id}:{resource}"
        now = time.time()
        window_start = now - window_seconds

        # Use Redis pipeline for atomic operations
        pipe = self.redis.pipeline()

        # Remove old entries outside window
        pipe.zremrangebyscore(key, 0, window_start)

        # Count current tokens in window
        pipe.zcard(key)

        # Execute pipeline
        results = await pipe.execute()
        current_count = results[1]

        # Check if we can add tokens
        if current_count + tokens <= max_tokens:
            # Add tokens with current timestamp
            for _ in range(tokens):
                await self.redis.zadd(key, {str(now + _): now + _})

            # Set expiry on key
            await self.redis.expire(key, window_seconds)

            allowed = True
            tokens_remaining = max_tokens - current_count - tokens
        else:
            allowed = False
            tokens_remaining = max_tokens - current_count

        # Calculate reset time
        if current_count > 0:
            oldest_score = await self.redis.zrange(key, 0, 0, withscores=True)
            if oldest_score:
                reset_time = oldest_score[0][1] + window_seconds
            else:
                reset_time = now + window_seconds
        else:
            reset_time = now + window_seconds

        metadata = {
            "tokens_remaining": max(0, tokens_remaining),
            "max_tokens": max_tokens,
            "window_seconds": window_seconds,
            "reset_time": datetime.fromtimestamp(reset_time).isoformat(),
            "retry_after_seconds": max(0, reset_time - now) if not allowed else 0,
        }

        return allowed, metadata

    async def get_usage_stats(
        self, tenant_id: str, resource: str, window_seconds: int = 60
    ) -> dict[str, any]:
        """Get current usage statistics.

        Args:
            tenant_id: Tenant identifier
            resource: Resource type
            window_seconds: Time window

        Returns:
            Usage statistics
        """
        key = f"rate_limit:{tenant_id}:{resource}"
        now = time.time()
        window_start = now - window_seconds

        # Clean old entries and count current
        await self.redis.zremrangebyscore(key, 0, window_start)
        current_count = await self.redis.zcard(key)

        # Get distribution over time
        entries = await self.redis.zrangebyscore(key, window_start, now, withscores=True)

        # Calculate rate
        if entries:
            time_span = entries[-1][1] - entries[0][1]
            rate = len(entries) / max(1, time_span) if time_span > 0 else 0
        else:
            rate = 0

        return {
            "current_usage": current_count,
            "rate_per_second": rate,
            "window_seconds": window_seconds,
            "timestamp": datetime.utcnow().isoformat(),
        }


class UsageTracker:
    """Track detailed usage metrics for billing and analytics."""

    def __init__(self, redis_client, db_session=None):
        self.redis = redis_client
        self.db = db_session

    async def track_usage(
        self, tenant_id: str, metric_type: str, amount: float, metadata: dict | None = None
    ):
        """Track usage metric.

        Args:
            tenant_id: Tenant identifier
            metric_type: Type of metric (tokens, api_calls, storage_mb)
            amount: Amount to track
            metadata: Additional metadata
        """
        timestamp = datetime.utcnow()

        # Track in Redis for real-time
        daily_key = f"usage:{tenant_id}:{timestamp.strftime('%Y-%m-%d')}:{metric_type}"
        monthly_key = f"usage:{tenant_id}:{timestamp.strftime('%Y-%m')}:{metric_type}"

        await self.redis.incrbyfloat(daily_key, amount)
        await self.redis.incrbyfloat(monthly_key, amount)

        # Set expiry
        await self.redis.expire(daily_key, 86400 * 7)  # 7 days
        await self.redis.expire(monthly_key, 86400 * 35)  # 35 days

        # Store detailed record in database if available
        if self.db:
            await self._store_usage_record(tenant_id, metric_type, amount, timestamp, metadata)

    async def _store_usage_record(
        self,
        tenant_id: str,
        metric_type: str,
        amount: float,
        timestamp: datetime,
        metadata: dict | None,
    ):
        """Store usage record in database.

        Args:
            tenant_id: Tenant identifier
            metric_type: Metric type
            amount: Usage amount
            timestamp: Timestamp
            metadata: Additional data
        """
        try:
            from api.models import Usage

            usage = Usage(
                tenant_id=tenant_id,
                metric_type=metric_type,
                amount=amount,
                timestamp=timestamp,
                metadata=metadata or {},
            )

            self.db.add(usage)
            await self.db.commit()

        except Exception as e:
            logger.error(f"Failed to store usage record: {e}")

    async def get_usage_summary(self, tenant_id: str, period: str = "day") -> dict[str, any]:
        """Get usage summary for period.

        Args:
            tenant_id: Tenant identifier
            period: Time period (day, month)

        Returns:
            Usage summary
        """
        timestamp = datetime.utcnow()

        if period == "day":
            pattern = f"usage:{tenant_id}:{timestamp.strftime('%Y-%m-%d')}:*"
        else:
            pattern = f"usage:{tenant_id}:{timestamp.strftime('%Y-%m')}:*"

        # Get all keys matching pattern
        keys = await self.redis.keys(pattern)

        summary = {}
        for key in keys:
            metric_type = key.split(":")[-1]
            value = await self.redis.get(key)
            summary[metric_type] = float(value) if value else 0

        return {
            "tenant_id": tenant_id,
            "period": period,
            "usage": summary,
            "timestamp": timestamp.isoformat(),
        }

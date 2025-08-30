"""Token bucket rate limiter for per-tenant rate limiting."""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: int
    refill_rate: float
    tokens: float
    last_refill: float

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from bucket."""
        self.refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def refill(self) -> None:
        """Refill bucket based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now


class TenantRateLimiter:
    """Per-tenant rate limiter using token bucket algorithm."""

    def __init__(self) -> None:
        self.buckets: Dict[str, Dict[str, TokenBucket]] = {}
        self.lock = asyncio.Lock()

    async def check_rate_limit(
        self, tenant_id: str, resource: str, tokens: int = 1, tier: str = "basic"
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is within rate limits."""
        async with self.lock:
            bucket = self._get_or_create_bucket(tenant_id, resource, tier)
            allowed = bucket.consume(tokens)
            wait_time = 0.0
            if not allowed:
                tokens_needed = tokens - bucket.tokens
                wait_time = tokens_needed / bucket.refill_rate

            metadata = {
                "tokens_remaining": int(bucket.tokens),
                "capacity": bucket.capacity,
                "refill_rate": bucket.refill_rate,
                "wait_time_seconds": wait_time,
                "retry_after": (
                    datetime.utcnow() + timedelta(seconds=wait_time) if wait_time > 0 else None
                ),
            }
            return allowed, metadata

    def _get_or_create_bucket(self, tenant_id: str, resource: str, tier: str) -> TokenBucket:
        """Get or create token bucket for tenant/resource."""
        if tenant_id not in self.buckets:
            self.buckets[tenant_id] = {}

        if resource not in self.buckets[tenant_id]:
            limits = self._get_resource_limits(resource, tier)
            capacity = int(limits["capacity"])
            self.buckets[tenant_id][resource] = TokenBucket(
                capacity=capacity,
                refill_rate=limits["refill_rate"],
                tokens=float(capacity),
                last_refill=time.time(),
            )
        return self.buckets[tenant_id][resource]

    def _get_resource_limits(self, resource: str, tier: str) -> Dict[str, float]:
        """Get rate limits for resource and tier."""
        limits = {
            "api_requests": {
                "basic": {"capacity": 100, "refill_rate": 1.67},
                "professional": {"capacity": 300, "refill_rate": 5.0},
                "enterprise": {"capacity": 1000, "refill_rate": 16.67},
            },
            "tokens": {
                "basic": {"capacity": 10000, "refill_rate": 166.67},
                "professional": {"capacity": 50000, "refill_rate": 833.33},
                "enterprise": {"capacity": 200000, "refill_rate": 3333.33},
            },
            "websocket_messages": {
                "basic": {"capacity": 60, "refill_rate": 1.0},
                "professional": {"capacity": 180, "refill_rate": 3.0},
                "enterprise": {"capacity": 600, "refill_rate": 10.0},
            },
            "file_uploads": {
                "basic": {"capacity": 10, "refill_rate": 0.167},
                "professional": {"capacity": 50, "refill_rate": 0.833},
                "enterprise": {"capacity": 200, "refill_rate": 3.33},
            },
        }
        resource_limits = limits.get(resource, limits["api_requests"])
        return resource_limits.get(tier, resource_limits["basic"])

    async def get_tenant_status(self, tenant_id: str) -> Dict[str, Dict[str, Any]]:
        """Get current rate limit status for tenant."""
        async with self.lock:
            if tenant_id not in self.buckets:
                return {}
            status = {}
            for resource, bucket in self.buckets[tenant_id].items():
                bucket.refill()
                status[resource] = {
                    "tokens_available": int(bucket.tokens),
                    "capacity": bucket.capacity,
                    "refill_rate": bucket.refill_rate,
                }
            return status

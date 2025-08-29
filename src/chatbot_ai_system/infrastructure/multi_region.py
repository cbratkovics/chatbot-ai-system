"""
Multi-Region Architecture with Failover Implementation
Provides cross-region replication, geographic load balancing, and automated failover
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aioredis
import httpx
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# Metrics
region_requests = Counter("region_requests_total", "Total requests per region", ["region"])
failover_events = Counter(
    "failover_events_total", "Total failover events", ["from_region", "to_region"]
)
region_latency = Histogram("region_latency_seconds", "Latency per region", ["region"])
region_health = Gauge("region_health_status", "Health status per region", ["region"])


class RegionStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNAVAILABLE = "unavailable"


@dataclass
class Region:
    name: str
    endpoint: str
    priority: int
    redis_endpoint: str
    is_primary: bool = False
    status: RegionStatus = RegionStatus.HEALTHY
    last_health_check: float = 0
    latency_ms: float = 0
    error_rate: float = 0


@dataclass
class FailoverConfig:
    health_check_interval: int = 10  # seconds
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2
    max_latency_ms: float = 1000
    max_error_rate: float = 0.1
    rto_seconds: int = 30  # Recovery Time Objective


class MultiRegionManager:
    """
    Manages multi-region architecture with automatic failover and cross-region replication
    """

    def __init__(self, regions: list[dict[str, Any]], config: FailoverConfig):
        self.regions = {region["name"]: Region(**region) for region in regions}
        self.config = config
        self.current_primary = self._get_primary_region()
        self.redis_connections: dict[str, aioredis.Redis] = {}
        self.health_check_failures: dict[str, int] = {r: 0 for r in self.regions}
        self._health_check_task: asyncio.Task | None = None
        self._replication_task: asyncio.Task | None = None

    async def initialize(self):
        """Initialize connections to all regions"""
        for region_name, region in self.regions.items():
            try:
                # Initialize Redis connections with connection pooling
                pool = aioredis.ConnectionPool.from_url(
                    region.redis_endpoint,
                    max_connections=50,
                    decode_responses=True,
                    retry_on_timeout=True,
                    socket_keepalive=True,
                    socket_keepalive_options={
                        1: 1,  # TCP_KEEPIDLE
                        2: 30,  # TCP_KEEPINTVL
                        3: 5,  # TCP_KEEPCNT
                    },
                )
                self.redis_connections[region_name] = aioredis.Redis(connection_pool=pool)

                # Test connection
                await self.redis_connections[region_name].ping()
                logger.info(f"Initialized connection to region {region_name}")

            except Exception as e:
                logger.error(f"Failed to initialize region {region_name}: {e}")
                region.status = RegionStatus.UNAVAILABLE

        # Start background tasks
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._replication_task = asyncio.create_task(self._replication_loop())

    async def close(self):
        """Clean up connections"""
        if self._health_check_task:
            self._health_check_task.cancel()
        if self._replication_task:
            self._replication_task.cancel()

        for redis_conn in self.redis_connections.values():
            await redis_conn.close()

    def _get_primary_region(self) -> str | None:
        """Get current primary region"""
        for name, region in self.regions.items():
            if region.is_primary and region.status == RegionStatus.HEALTHY:
                return name

        # If no healthy primary, find best alternative
        return self._find_best_region()

    def _find_best_region(self) -> str | None:
        """Find best available region based on priority and health"""
        healthy_regions = [
            (name, region)
            for name, region in self.regions.items()
            if region.status in [RegionStatus.HEALTHY, RegionStatus.DEGRADED]
        ]

        if not healthy_regions:
            return None

        # Sort by priority and latency
        healthy_regions.sort(key=lambda x: (x[1].priority, x[1].latency_ms))
        return healthy_regions[0][0] if healthy_regions else None

    async def _health_check_loop(self):
        """Background task for health checking all regions"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._check_all_regions_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _check_all_regions_health(self):
        """Check health of all regions"""
        tasks = [self._check_region_health(region_name) for region_name in self.regions]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_region_health(self, region_name: str) -> bool:
        """Check health of a specific region"""
        region = self.regions[region_name]
        start_time = time.time()

        try:
            # Check Redis connectivity
            redis_conn = self.redis_connections.get(region_name)
            if redis_conn:
                await asyncio.wait_for(redis_conn.ping(), timeout=2.0)

            # Check API endpoint
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{region.endpoint}/health", timeout=5.0)
                response.raise_for_status()

            # Calculate latency
            latency = (time.time() - start_time) * 1000
            region.latency_ms = latency

            # Update status based on latency
            if latency > self.config.max_latency_ms:
                self._mark_region_degraded(region_name, f"High latency: {latency:.0f}ms")
            else:
                self._mark_region_healthy(region_name)

            region_latency.labels(region=region_name).observe(latency / 1000)
            return True

        except Exception as e:
            logger.warning(f"Health check failed for {region_name}: {e}")
            self._mark_region_unhealthy(region_name, str(e))
            return False

    def _mark_region_healthy(self, region_name: str):
        """Mark region as healthy"""
        region = self.regions[region_name]
        self.health_check_failures[region_name] = 0

        if region.status != RegionStatus.HEALTHY:
            logger.info(f"Region {region_name} is now healthy")
            region.status = RegionStatus.HEALTHY
            region_health.labels(region=region_name).set(1)

    def _mark_region_degraded(self, region_name: str, reason: str):
        """Mark region as degraded"""
        region = self.regions[region_name]

        if region.status != RegionStatus.DEGRADED:
            logger.warning(f"Region {region_name} degraded: {reason}")
            region.status = RegionStatus.DEGRADED
            region_health.labels(region=region_name).set(0.5)

    def _mark_region_unhealthy(self, region_name: str, reason: str):
        """Mark region as unhealthy after threshold"""
        self.health_check_failures[region_name] += 1

        if self.health_check_failures[region_name] >= self.config.unhealthy_threshold:
            region = self.regions[region_name]

            if region.status != RegionStatus.UNHEALTHY:
                logger.error(f"Region {region_name} marked unhealthy: {reason}")
                region.status = RegionStatus.UNHEALTHY
                region_health.labels(region=region_name).set(0)

                # Trigger failover if this was the primary
                if region_name == self.current_primary:
                    asyncio.create_task(self._perform_failover())

    async def _perform_failover(self):
        """Perform automatic failover to best available region"""
        old_primary = self.current_primary
        new_primary = self._find_best_region()

        if not new_primary or new_primary == old_primary:
            logger.error("No suitable region for failover")
            return

        logger.info(f"Initiating failover from {old_primary} to {new_primary}")
        start_time = time.time()

        try:
            # Update primary designation
            if old_primary:
                self.regions[old_primary].is_primary = False
            self.regions[new_primary].is_primary = True
            self.current_primary = new_primary

            # Migrate active sessions
            await self._migrate_sessions(old_primary, new_primary)

            # Update DNS/load balancer (simulated)
            await self._update_traffic_routing(new_primary)

            failover_time = time.time() - start_time
            logger.info(f"Failover completed in {failover_time:.1f}s")

            if failover_time > self.config.rto_seconds:
                logger.warning(
                    f"Failover exceeded RTO: {failover_time:.1f}s > {self.config.rto_seconds}s"
                )

            failover_events.labels(from_region=old_primary, to_region=new_primary).inc()

        except Exception as e:
            logger.error(f"Failover failed: {e}")
            # Attempt rollback
            self.current_primary = old_primary
            if old_primary:
                self.regions[old_primary].is_primary = True
            self.regions[new_primary].is_primary = False

    async def _migrate_sessions(self, from_region: str | None, to_region: str):
        """Migrate active sessions between regions"""
        if not from_region or from_region not in self.redis_connections:
            return

        from_redis = self.redis_connections[from_region]
        to_redis = self.redis_connections[to_region]

        try:
            # Get all active session keys
            session_keys = await from_redis.keys("session:*")

            if not session_keys:
                return

            logger.info(f"Migrating {len(session_keys)} sessions from {from_region} to {to_region}")

            # Batch migrate sessions
            pipe = to_redis.pipeline()
            for key in session_keys:
                value = await from_redis.get(key)
                ttl = await from_redis.ttl(key)
                if value and ttl > 0:
                    pipe.setex(key, ttl, value)

            await pipe.execute()

        except Exception as e:
            logger.error(f"Session migration failed: {e}")

    async def _update_traffic_routing(self, new_primary: str):
        """Update traffic routing to new primary region"""
        # In production, this would update Route53/CloudFlare/load balancer
        # Here we simulate the DNS update
        logger.info(f"Updating traffic routing to {new_primary}")
        await asyncio.sleep(0.5)  # Simulate DNS propagation

    async def _replication_loop(self):
        """Background task for cross-region data replication"""
        while True:
            try:
                await asyncio.sleep(1)  # Replication interval
                await self._replicate_data()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Replication error: {e}")

    async def _replicate_data(self):
        """Replicate critical data across regions"""
        if not self.current_primary:
            return

        primary_redis = self.redis_connections.get(self.current_primary)
        if not primary_redis:
            return

        # Get keys that need replication
        replication_patterns = ["conversation:*", "user:*", "cache:*"]

        for pattern in replication_patterns:
            try:
                keys = await primary_redis.keys(pattern)

                for region_name, redis_conn in self.redis_connections.items():
                    if region_name == self.current_primary:
                        continue

                    # Async replication to secondary regions
                    asyncio.create_task(self._replicate_keys(primary_redis, redis_conn, keys))

            except Exception as e:
                logger.error(f"Replication failed for pattern {pattern}: {e}")

    async def _replicate_keys(
        self, source: aioredis.Redis, target: aioredis.Redis, keys: list[str]
    ):
        """Replicate specific keys from source to target"""
        if not keys:
            return

        pipe = target.pipeline()
        for key in keys:
            try:
                value = await source.get(key)
                ttl = await source.ttl(key)
                if value and ttl > 0:
                    pipe.setex(key, ttl, value)
            except Exception:
                continue

        try:
            await pipe.execute()
        except Exception as e:
            logger.error(f"Failed to replicate batch: {e}")

    async def get_redis_connection(
        self, prefer_region: str | None = None
    ) -> tuple[str, aioredis.Redis]:
        """Get Redis connection with automatic region selection"""
        region = prefer_region or self.current_primary or self._find_best_region()

        if not region or region not in self.redis_connections:
            raise Exception("No available regions")

        region_requests.labels(region=region).inc()
        return region, self.redis_connections[region]

    def get_current_status(self) -> dict[str, Any]:
        """Get current multi-region status"""
        return {
            "current_primary": self.current_primary,
            "regions": {
                name: {
                    "status": region.status.value,
                    "is_primary": region.is_primary,
                    "latency_ms": region.latency_ms,
                    "error_rate": region.error_rate,
                    "priority": region.priority,
                }
                for name, region in self.regions.items()
            },
            "config": {
                "health_check_interval": self.config.health_check_interval,
                "rto_seconds": self.config.rto_seconds,
                "max_latency_ms": self.config.max_latency_ms,
            },
        }

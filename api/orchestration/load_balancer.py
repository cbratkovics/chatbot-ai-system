"""Load balancer for distributing requests across provider instances."""

import asyncio
import hashlib
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""

    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    LEAST_RESPONSE_TIME = "least_response_time"
    RANDOM = "random"
    CONSISTENT_HASH = "consistent_hash"
    ADAPTIVE = "adaptive"


@dataclass
class ProviderInstance:
    """Represents a provider instance."""

    id: str
    provider: str
    model: str
    endpoint: str
    weight: int = 1
    max_connections: int = 100
    current_connections: int = 0
    total_requests: int = 0
    total_errors: int = 0
    avg_response_time_ms: float = 0
    last_error_time: datetime | None = None
    health_score: float = 1.0
    available: bool = True
    metadata: dict[str, Any] = None


class LoadBalancer:
    """Distributes requests across multiple provider instances."""

    def __init__(
        self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN
    ):
        """Initialize load balancer.

        Args:
            strategy: Load balancing strategy
        """
        self.strategy = strategy
        self.instances: dict[str, ProviderInstance] = {}
        self.round_robin_index = 0
        self.consistent_hash_ring = {}
        self.health_check_interval = 30  # seconds
        self.health_check_task = None

    def add_instance(self, instance: ProviderInstance):
        """Add provider instance to pool.

        Args:
            instance: Provider instance
        """
        self.instances[instance.id] = instance

        # Update consistent hash ring if using that strategy
        if self.strategy == LoadBalancingStrategy.CONSISTENT_HASH:
            self._update_hash_ring()

        logger.info(f"Added instance {instance.id} to load balancer")

    def remove_instance(self, instance_id: str):
        """Remove provider instance from pool.

        Args:
            instance_id: Instance identifier
        """
        if instance_id in self.instances:
            del self.instances[instance_id]

            if self.strategy == LoadBalancingStrategy.CONSISTENT_HASH:
                self._update_hash_ring()

            logger.info(f"Removed instance {instance_id} from load balancer")

    async def select_instance(
        self, request_key: str | None = None, required_model: str | None = None
    ) -> ProviderInstance | None:
        """Select instance based on strategy.

        Args:
            request_key: Key for consistent hashing
            required_model: Required model name

        Returns:
            Selected instance or None
        """
        # Filter available instances
        available = [
            inst
            for inst in self.instances.values()
            if inst.available and inst.current_connections < inst.max_connections
        ]

        # Filter by model if required
        if required_model:
            available = [inst for inst in available if inst.model == required_model]

        if not available:
            return None

        # Select based on strategy
        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._select_round_robin(available)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            return self._select_weighted_round_robin(available)
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._select_least_connections(available)
        elif self.strategy == LoadBalancingStrategy.LEAST_RESPONSE_TIME:
            return self._select_least_response_time(available)
        elif self.strategy == LoadBalancingStrategy.RANDOM:
            return self._select_random(available)
        elif self.strategy == LoadBalancingStrategy.CONSISTENT_HASH:
            return self._select_consistent_hash(available, request_key)
        elif self.strategy == LoadBalancingStrategy.ADAPTIVE:
            return self._select_adaptive(available)
        else:
            return available[0]

    def _select_round_robin(self, instances: list[ProviderInstance]) -> ProviderInstance:
        """Select using round-robin."""
        selected = instances[self.round_robin_index % len(instances)]
        self.round_robin_index += 1
        return selected

    def _select_weighted_round_robin(self, instances: list[ProviderInstance]) -> ProviderInstance:
        """Select using weighted round-robin."""
        # Build weighted list
        weighted_list = []
        for inst in instances:
            weighted_list.extend([inst] * inst.weight)

        if not weighted_list:
            return instances[0]

        selected = weighted_list[self.round_robin_index % len(weighted_list)]
        self.round_robin_index += 1
        return selected

    def _select_least_connections(self, instances: list[ProviderInstance]) -> ProviderInstance:
        """Select instance with least connections."""
        return min(instances, key=lambda x: x.current_connections)

    def _select_least_response_time(self, instances: list[ProviderInstance]) -> ProviderInstance:
        """Select instance with least response time."""
        return min(instances, key=lambda x: x.avg_response_time_ms)

    def _select_random(self, instances: list[ProviderInstance]) -> ProviderInstance:
        """Select random instance."""
        return random.choice(instances)

    def _select_consistent_hash(
        self, instances: list[ProviderInstance], request_key: str | None
    ) -> ProviderInstance:
        """Select using consistent hashing."""
        if not request_key:
            request_key = str(time.time())

        # Hash the key
        hash_value = int(hashlib.md5(request_key.encode()).hexdigest(), 16)

        # Find the appropriate instance in the ring
        sorted_hashes = sorted(self.consistent_hash_ring.keys())
        for h in sorted_hashes:
            if hash_value <= h:
                return self.consistent_hash_ring[h]

        # Wrap around to first instance
        return self.consistent_hash_ring[sorted_hashes[0]] if sorted_hashes else instances[0]

    def _select_adaptive(self, instances: list[ProviderInstance]) -> ProviderInstance:
        """Select using adaptive scoring."""
        # Score each instance
        scored_instances = []
        for inst in instances:
            score = self._calculate_instance_score(inst)
            scored_instances.append((inst, score))

        # Sort by score (highest first)
        scored_instances.sort(key=lambda x: x[1], reverse=True)

        # Use weighted random selection from top candidates
        top_candidates = scored_instances[:3]
        if not top_candidates:
            return instances[0]

        # Weighted random selection
        total_score = sum(score for _, score in top_candidates)
        if total_score == 0:
            return top_candidates[0][0]

        rand_value = random.uniform(0, total_score)
        cumulative = 0

        for inst, score in top_candidates:
            cumulative += score
            if rand_value <= cumulative:
                return inst

        return top_candidates[-1][0]

    def _calculate_instance_score(self, instance: ProviderInstance) -> float:
        """Calculate adaptive score for instance.

        Args:
            instance: Provider instance

        Returns:
            Score (higher is better)
        """
        score = instance.health_score

        # Connection availability factor
        connection_ratio = 1 - (instance.current_connections / instance.max_connections)
        score *= 0.5 + 0.5 * connection_ratio

        # Response time factor
        if instance.avg_response_time_ms > 0:
            response_factor = 1000 / (1000 + instance.avg_response_time_ms)
            score *= 0.7 + 0.3 * response_factor

        # Error rate factor
        if instance.total_requests > 0:
            error_rate = instance.total_errors / instance.total_requests
            score *= 1 - error_rate

        # Recent error penalty
        if instance.last_error_time:
            time_since_error = (datetime.utcnow() - instance.last_error_time).total_seconds()
            if time_since_error < 60:  # Recent error in last minute
                score *= 0.5
            elif time_since_error < 300:  # Error in last 5 minutes
                score *= 0.8

        return max(0, min(1, score))

    def _update_hash_ring(self):
        """Update consistent hash ring."""
        self.consistent_hash_ring = {}

        for inst in self.instances.values():
            # Add multiple virtual nodes for better distribution
            for i in range(inst.weight * 10):
                key = f"{inst.id}:{i}"
                hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)
                self.consistent_hash_ring[hash_value] = inst

    async def mark_request_start(self, instance_id: str):
        """Mark start of request to instance.

        Args:
            instance_id: Instance identifier
        """
        if instance_id in self.instances:
            self.instances[instance_id].current_connections += 1
            self.instances[instance_id].total_requests += 1

    async def mark_request_end(self, instance_id: str, success: bool, response_time_ms: float):
        """Mark end of request to instance.

        Args:
            instance_id: Instance identifier
            success: Whether request succeeded
            response_time_ms: Response time in milliseconds
        """
        if instance_id not in self.instances:
            return

        instance = self.instances[instance_id]

        # Update connections
        instance.current_connections = max(0, instance.current_connections - 1)

        # Update errors
        if not success:
            instance.total_errors += 1
            instance.last_error_time = datetime.utcnow()

        # Update response time (exponential moving average)
        alpha = 0.1
        instance.avg_response_time_ms = (
            1 - alpha
        ) * instance.avg_response_time_ms + alpha * response_time_ms

        # Update health score
        await self._update_health_score(instance)

    async def _update_health_score(self, instance: ProviderInstance):
        """Update health score for instance.

        Args:
            instance: Provider instance
        """
        # Base health score
        score = 1.0

        # Error rate impact
        if instance.total_requests > 10:
            error_rate = instance.total_errors / instance.total_requests
            score *= 1 - error_rate

        # Response time impact
        if instance.avg_response_time_ms > 5000:  # > 5 seconds
            score *= 0.5
        elif instance.avg_response_time_ms > 2000:  # > 2 seconds
            score *= 0.8

        # Connection saturation impact
        saturation = instance.current_connections / instance.max_connections
        if saturation > 0.9:
            score *= 0.7
        elif saturation > 0.7:
            score *= 0.9

        instance.health_score = max(0.1, min(1.0, score))

        # Mark as unavailable if health is too low
        if instance.health_score < 0.2:
            instance.available = False
            logger.warning(
                f"Instance {instance.id} marked unavailable (health: {instance.health_score:.2f})"
            )

    async def start_health_checks(self, check_func: Callable):
        """Start periodic health checks.

        Args:
            check_func: Function to check instance health
        """
        self.health_check_task = asyncio.create_task(self._health_check_loop(check_func))

    async def _health_check_loop(self, check_func: Callable):
        """Health check loop.

        Args:
            check_func: Health check function
        """
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)

                # Check each instance
                tasks = []
                for instance in self.instances.values():
                    task = asyncio.create_task(self._check_instance_health(instance, check_func))
                    tasks.append(task)

                await asyncio.gather(*tasks, return_exceptions=True)

            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _check_instance_health(self, instance: ProviderInstance, check_func: Callable):
        """Check health of single instance.

        Args:
            instance: Provider instance
            check_func: Health check function
        """
        try:
            start_time = time.time()
            is_healthy = await check_func(instance)
            response_time = (time.time() - start_time) * 1000

            instance.available = is_healthy

            if is_healthy:
                # Update response time from health check
                alpha = 0.05
                instance.avg_response_time_ms = (
                    1 - alpha
                ) * instance.avg_response_time_ms + alpha * response_time

                # Improve health score
                instance.health_score = min(1.0, instance.health_score * 1.1)
            else:
                # Degrade health score
                instance.health_score = max(0.1, instance.health_score * 0.8)
                instance.last_error_time = datetime.utcnow()

        except Exception as e:
            logger.error(f"Health check failed for {instance.id}: {e}")
            instance.available = False
            instance.health_score = max(0.1, instance.health_score * 0.5)

    def get_instance_stats(self, instance_id: str) -> dict[str, Any] | None:
        """Get statistics for instance.

        Args:
            instance_id: Instance identifier

        Returns:
            Instance statistics
        """
        if instance_id not in self.instances:
            return None

        instance = self.instances[instance_id]

        return {
            "id": instance.id,
            "provider": instance.provider,
            "model": instance.model,
            "available": instance.available,
            "health_score": instance.health_score,
            "current_connections": instance.current_connections,
            "max_connections": instance.max_connections,
            "total_requests": instance.total_requests,
            "total_errors": instance.total_errors,
            "error_rate": instance.total_errors / max(1, instance.total_requests),
            "avg_response_time_ms": instance.avg_response_time_ms,
            "last_error": instance.last_error_time.isoformat()
            if instance.last_error_time
            else None,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get overall load balancer statistics.

        Returns:
            Statistics dictionary
        """
        total_instances = len(self.instances)
        available_instances = sum(1 for i in self.instances.values() if i.available)
        total_connections = sum(i.current_connections for i in self.instances.values())
        total_requests = sum(i.total_requests for i in self.instances.values())
        total_errors = sum(i.total_errors for i in self.instances.values())

        avg_health = 0
        if total_instances > 0:
            avg_health = sum(i.health_score for i in self.instances.values()) / total_instances

        return {
            "strategy": self.strategy.value,
            "total_instances": total_instances,
            "available_instances": available_instances,
            "total_connections": total_connections,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": total_errors / max(1, total_requests),
            "average_health_score": avg_health,
            "instances": [self.get_instance_stats(inst_id) for inst_id in self.instances],
        }

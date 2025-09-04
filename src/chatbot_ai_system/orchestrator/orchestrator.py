"""Provider orchestrator with resilience patterns and intelligent routing."""

import asyncio
import hashlib
import json
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List
from uuid import UUID

import structlog

from chatbot_ai_system.providers.base import (
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderError,
    RateLimitError,
)
from chatbot_ai_system.telemetry.metrics import metrics_collector

logger = structlog.get_logger()


class RoutingStrategy(str, Enum):
    """Provider routing strategies."""

    ROUND_ROBIN = "round_robin"
    LEAST_LATENCY = "least_latency"
    LEAST_COST = "least_cost"
    WEIGHTED_RANDOM = "weighted_random"
    FAILOVER = "failover"
    LOAD_BALANCED = "load_balanced"


class CacheStrategy(str, Enum):
    """Cache strategies."""

    NONE = "none"
    SEMANTIC = "semantic"
    EXACT = "exact"
    HYBRID = "hybrid"


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""

    routing_strategy: RoutingStrategy = RoutingStrategy.LOAD_BALANCED
    cache_strategy: CacheStrategy = CacheStrategy.HYBRID
    cache_ttl: int = 3600  # 1 hour

    # Failover configuration
    enable_failover: bool = True
    failover_timeout: int = 5  # Seconds to wait before failover
    max_failover_attempts: int = 3

    # Rate limiting
    global_rate_limit: int = 100  # Requests per minute
    per_tenant_rate_limit: int = 50  # Requests per minute per tenant

    # Load balancing
    load_balance_window: int = 60  # Seconds to consider for load metrics
    health_check_interval: int = 30  # Seconds between health checks

    # Idempotency
    enable_idempotency: bool = True
    idempotency_key_ttl: int = 86400  # 24 hours

    # Cost optimization
    max_cost_per_request: float = 1.0  # Maximum cost in USD
    cost_optimization_enabled: bool = True


@dataclass
class ProviderWeight:
    """Weight configuration for a provider."""

    provider: BaseProvider
    weight: float = 1.0
    priority: int = 0  # Lower is higher priority
    max_requests_per_minute: int = 100
    current_requests: int = 0
    last_reset: datetime = field(default_factory=datetime.now)


class RequestCache:
    """Cache for request responses with semantic matching."""

    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self.cache: dict[str, tuple[CompletionResponse, datetime]] = {}
        self.semantic_cache: dict[str, list[tuple[str, CompletionResponse, datetime]]] = {}
        self._lock = asyncio.Lock()

    def _generate_key(self, request: CompletionRequest) -> str:
        """Generate cache key from request."""
        key_data = {
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "model": request.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def _generate_semantic_key(self, content: str) -> str:
        """Generate semantic key from content (simplified)."""
        # In production, use embeddings for semantic similarity
        words = content.lower().split()[:10]  # Use first 10 words
        return " ".join(sorted(words))

    async def get(
        self, request: CompletionRequest, strategy: CacheStrategy
    ) -> CompletionResponse | None:
        """Get cached response if available."""
        async with self._lock:
            now = datetime.now()

            # Exact match
            if strategy in [CacheStrategy.EXACT, CacheStrategy.HYBRID]:
                key = self._generate_key(request)
                if key in self.cache:
                    response, timestamp = self.cache[key]
                    if (now - timestamp).seconds < self.ttl:
                        logger.info("Cache hit (exact)", cache_key=key[:8])
                        response.cached = True
                        metrics_collector.record_cache_hit("exact")
                        return response
                    else:
                        del self.cache[key]

            # Semantic match
            if strategy in [CacheStrategy.SEMANTIC, CacheStrategy.HYBRID]:
                if request.messages:
                    last_message = request.messages[-1].content
                    semantic_key = self._generate_semantic_key(last_message)

                    if semantic_key in self.semantic_cache:
                        candidates = self.semantic_cache[semantic_key]
                        for cached_content, response, timestamp in candidates:
                            if (now - timestamp).seconds < self.ttl:
                                # Simple similarity check (in production, use embeddings)
                                if len(set(last_message.split()) & set(cached_content.split())) > 5:
                                    logger.info("Cache hit (semantic)", cache_key=semantic_key[:20])
                                    response.cached = True
                                    metrics_collector.record_cache_hit("semantic")
                                    return response

            metrics_collector.record_cache_miss()
            return None

    async def set(self, request: CompletionRequest, response: CompletionResponse):
        """Cache a response."""
        async with self._lock:
            now = datetime.now()

            # Exact cache
            key = self._generate_key(request)
            self.cache[key] = (response, now)

            # Semantic cache
            if request.messages:
                last_message = request.messages[-1].content
                semantic_key = self._generate_semantic_key(last_message)

                if semantic_key not in self.semantic_cache:
                    self.semantic_cache[semantic_key] = []

                self.semantic_cache[semantic_key].append((last_message, response, now))

                # Limit semantic cache size
                if len(self.semantic_cache[semantic_key]) > 10:
                    self.semantic_cache[semantic_key] = self.semantic_cache[semantic_key][-10:]

    async def clear_expired(self):
        """Clear expired cache entries."""
        async with self._lock:
            now = datetime.now()

            # Clear exact cache
            expired_keys = [
                key
                for key, (_, timestamp) in self.cache.items()
                if (now - timestamp).seconds >= self.ttl
            ]
            for key in expired_keys:
                del self.cache[key]

            # Clear semantic cache
            for semantic_key in list(self.semantic_cache.keys()):
                self.semantic_cache[semantic_key] = [
                    (content, response, timestamp)
                    for content, response, timestamp in self.semantic_cache[semantic_key]
                    if (now - timestamp).seconds < self.ttl
                ]
                if not self.semantic_cache[semantic_key]:
                    del self.semantic_cache[semantic_key]


class IdempotencyManager:
    """Manage idempotent requests."""

    def __init__(self, ttl: int = 86400):
        self.ttl = ttl
        self.requests: dict[str, tuple[CompletionResponse, datetime]] = {}
        self._lock = asyncio.Lock()

    async def get_cached_response(self, key: str) -> CompletionResponse | None:
        """Get cached response for idempotency key."""
        async with self._lock:
            if key in self.requests:
                response, timestamp = self.requests[key]
                if (datetime.now() - timestamp).seconds < self.ttl:
                    logger.info("Idempotent request served", key=key)
                    return response
                else:
                    del self.requests[key]
            return None

    async def store_response(self, key: str, response: CompletionResponse):
        """Store response for idempotency key."""
        async with self._lock:
            self.requests[key] = (response, datetime.now())


class ProviderOrchestrator:
    """Orchestrates multiple providers with resilience patterns."""

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.providers: list[ProviderWeight] = []
        self.cache = RequestCache(config.cache_ttl)
        self.idempotency_manager = IdempotencyManager(config.idempotency_key_ttl)

        # Routing state
        self.round_robin_index = 0
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.request_timestamps: Dict[str, List[float]] = defaultdict(list)

        # Health check task
        self._health_check_task: asyncio.Task | None = None
        self._running = False

    def add_provider(
        self,
        provider: BaseProvider,
        weight: float = 1.0,
        priority: int = 0,
        max_rpm: int = 100,
    ):
        """Add a provider to the orchestrator."""
        provider_weight = ProviderWeight(
            provider=provider,
            weight=weight,
            priority=priority,
            max_requests_per_minute=max_rpm,
        )
        self.providers.append(provider_weight)
        self.providers.sort(key=lambda p: p.priority)
        logger.info(
            "Provider added",
            provider=provider.name,
            weight=weight,
            priority=priority,
        )

    async def start(self):
        """Start the orchestrator background tasks."""
        if self._running:
            return

        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._cache_cleanup_loop())
        asyncio.create_task(self._rate_limit_reset_loop())
        logger.info("Orchestrator started")

    async def stop(self):
        """Stop the orchestrator background tasks."""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Orchestrator stopped")

    async def _health_check_loop(self):
        """Periodically check provider health."""
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._check_all_providers_health()
            except Exception as e:
                logger.error("Health check error", error=str(e))

    async def _cache_cleanup_loop(self):
        """Periodically clean up expired cache entries."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Every hour
                await self.cache.clear_expired()
            except Exception as e:
                logger.error("Cache cleanup error", error=str(e))

    async def _rate_limit_reset_loop(self):
        """Reset rate limit counters."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Every minute
                for pw in self.providers:
                    pw.current_requests = 0
                    pw.last_reset = datetime.now()
                self.request_counts.clear()

                # Clean old timestamps
                now = time.time()
                for tenant_id in list(self.request_timestamps.keys()):
                    self.request_timestamps[tenant_id] = [
                        ts for ts in self.request_timestamps[tenant_id] if now - ts < 60
                    ]
            except Exception as e:
                logger.error("Rate limit reset error", error=str(e))

    async def _check_all_providers_health(self):
        """Check health of all providers."""
        tasks = [provider.provider.health_check() for provider in self.providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for provider, result in zip(self.providers, results, strict=False):
            if isinstance(result, Exception):
                logger.warning(
                    "Provider health check failed",
                    provider=provider.provider.name,
                    error=str(result),
                )
            else:
                logger.debug(
                    "Provider health",
                    provider=provider.provider.name,
                    status=result.get("status"),
                )

    def _select_provider(self, request: CompletionRequest) -> BaseProvider | None:
        """Select a provider based on routing strategy."""
        available_providers = [
            pw
            for pw in self.providers
            if pw.provider.is_healthy() and pw.provider.supports_model(request.model)
        ]

        if not available_providers:
            return None

        # Check rate limits
        available_providers = [
            pw for pw in available_providers if pw.current_requests < pw.max_requests_per_minute
        ]

        if not available_providers:
            return None

        if self.config.routing_strategy == RoutingStrategy.ROUND_ROBIN:
            provider = available_providers[self.round_robin_index % len(available_providers)]
            self.round_robin_index += 1

        elif self.config.routing_strategy == RoutingStrategy.LEAST_LATENCY:
            provider = min(
                available_providers,
                key=lambda pw: pw.provider.metrics.average_latency,
            )

        elif self.config.routing_strategy == RoutingStrategy.LEAST_COST:
            # Select based on cost for the model
            provider = min(
                available_providers,
                key=lambda pw: pw.provider.config.prompt_cost_per_1k,
            )

        elif self.config.routing_strategy == RoutingStrategy.WEIGHTED_RANDOM:
            weights = [pw.weight for pw in available_providers]
            provider = random.choices(available_providers, weights=weights, k=1)[0]

        elif self.config.routing_strategy == RoutingStrategy.FAILOVER:
            # Use first available by priority
            provider = available_providers[0]

        elif self.config.routing_strategy == RoutingStrategy.LOAD_BALANCED:
            # Select based on current load
            provider = min(
                available_providers,
                key=lambda pw: pw.current_requests / pw.max_requests_per_minute,
            )

        else:
            provider = available_providers[0]

        provider.current_requests += 1
        return provider.provider

    async def _check_rate_limit(self, tenant_id: UUID | None) -> bool:
        """Check if request is within rate limits."""
        now = time.time()

        # Global rate limit
        global_count = sum(len(timestamps) for timestamps in self.request_timestamps.values())
        if global_count >= self.config.global_rate_limit:
            return False

        # Per-tenant rate limit
        if tenant_id:
            tenant_key = str(tenant_id)
            self.request_timestamps[tenant_key] = [
                ts for ts in self.request_timestamps[tenant_key] if now - ts < 60
            ]

            if len(self.request_timestamps[tenant_key]) >= self.config.per_tenant_rate_limit:
                return False

            self.request_timestamps[tenant_key].append(now)

        return True

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Complete a request with orchestration."""
        start_time = time.time()

        # Check idempotency
        if self.config.enable_idempotency and request.metadata:
            idempotency_key = request.metadata.get("idempotency_key")
            if idempotency_key:
                cached_response = await self.idempotency_manager.get_cached_response(
                    idempotency_key
                )
                if cached_response:
                    return cached_response

        # Check rate limits
        if not await self._check_rate_limit(request.tenant_id):
            raise RateLimitError(
                "Rate limit exceeded",
                retry_after=60,
                provider_name="orchestrator",
            )

        # Check cache
        cached_response = await self.cache.get(request, self.config.cache_strategy)
        if cached_response:
            return cached_response

        # Cost check
        if self.config.cost_optimization_enabled:
            # Estimate cost and check against limit
            estimated_tokens = len(str(request.messages)) / 4  # Rough estimate
            estimated_cost = estimated_tokens * 0.002 / 1000
            if estimated_cost > self.config.max_cost_per_request:
                raise ProviderError(
                    f"Estimated cost ${estimated_cost:.4f} exceeds limit",
                    error_code="cost_limit",
                    retryable=False,
                )

        # Try providers with failover
        last_error = None
        attempts = 0

        while attempts < self.config.max_failover_attempts:
            provider = self._select_provider(request)
            if not provider:
                raise ProviderError(
                    "No available providers",
                    error_code="no_providers",
                    retryable=True,
                )

            try:
                logger.info(
                    "Routing request",
                    provider=provider.name,
                    model=request.model,
                    attempt=attempts + 1,
                )

                response = await provider.complete(request)

                # Cache successful response
                await self.cache.set(request, response)

                # Store for idempotency
                if self.config.enable_idempotency and request.metadata:
                    idempotency_key = request.metadata.get("idempotency_key")
                    if idempotency_key:
                        await self.idempotency_manager.store_response(idempotency_key, response)

                # Record metrics
                latency_ms = (time.time() - start_time) * 1000
                metrics_collector.record_request(
                    provider=provider.name,
                    model=request.model,
                    latency_ms=latency_ms,
                    tokens=response.usage.total_tokens,
                    cost=response.usage.total_cost,
                    success=True,
                )

                return response

            except ProviderError as e:
                last_error = e
                logger.warning(
                    "Provider failed",
                    provider=provider.name,
                    error=str(e),
                    attempt=attempts + 1,
                )

                if not e.retryable:
                    raise

                attempts += 1

                if attempts < self.config.max_failover_attempts:
                    await asyncio.sleep(self.config.failover_timeout)

        # All attempts failed
        raise ProviderError(
            f"All providers failed after {attempts} attempts",
            error_code="all_failed",
            retryable=False,
        ) from last_error

    async def complete_stream(self, request: CompletionRequest):
        """Stream a completion with orchestration."""
        # Similar to complete but with streaming
        # For brevity, implementing basic version
        provider = self._select_provider(request)
        if not provider:
            raise ProviderError(
                "No available providers",
                error_code="no_providers",
                retryable=True,
            )

        async for chunk in provider.complete_stream(request):
            yield chunk

    async def get_status(self) -> dict[str, Any]:
        """Get orchestrator status."""
        provider_statuses = []
        for pw in self.providers:
            health = await pw.provider.health_check()
            provider_statuses.append(
                {
                    "name": pw.provider.name,
                    "weight": pw.weight,
                    "priority": pw.priority,
                    "status": health["status"],
                    "current_requests": pw.current_requests,
                    "max_rpm": pw.max_requests_per_minute,
                }
            )

        return {
            "config": {
                "routing_strategy": self.config.routing_strategy.value,
                "cache_strategy": self.config.cache_strategy.value,
                "failover_enabled": self.config.enable_failover,
            },
            "providers": provider_statuses,
            "cache_stats": {
                "entries": len(self.cache.cache),
                "semantic_keys": len(self.cache.semantic_cache),
            },
            "idempotency_keys": len(self.idempotency_manager.requests),
        }

"""Provider orchestration with intelligent routing and failover."""

import asyncio
import logging
import random
from collections.abc import AsyncIterator

from .base import (
    BaseProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderError,
    RateLimitError,
    StreamChunk,
)
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class LoadBalancingStrategy:
    """Load balancing strategies for provider selection."""

    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_LATENCY = "least_latency"
    LEAST_LOADED = "least_loaded"
    RANDOM = "random"


class ProviderOrchestrator:
    """Orchestrates multiple providers with intelligent routing and failover."""

    def __init__(
        self,
        providers: list[BaseProvider],
        strategy: str = LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN,
        max_retries: int = 3,
        timeout: float = 30.0,
        enable_circuit_breaker: bool = True,
    ):
        self.providers = {provider.name: provider for provider in providers}
        self.strategy = strategy
        self.max_retries = max_retries
        self.timeout = timeout
        self.enable_circuit_breaker = enable_circuit_breaker

        # Circuit breakers for each provider
        self.circuit_breakers = {}
        if enable_circuit_breaker:
            for provider in providers:
                self.circuit_breakers[provider.name] = CircuitBreaker(
                    failure_threshold=5, recovery_timeout=60, expected_exception=ProviderError
                )

        # Round robin state
        self._round_robin_index = 0

        # Performance tracking
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.failover_count = 0

        logger.info(f"Orchestrator initialized with {len(providers)} providers using {strategy}")

    def get_healthy_providers(self) -> list[BaseProvider]:
        """Get list of healthy providers."""
        healthy = []

        for provider in self.providers.values():
            # Check circuit breaker state
            if self.enable_circuit_breaker:
                circuit_breaker = self.circuit_breakers[provider.name]
                if circuit_breaker.state == "open":
                    logger.debug(f"Provider {provider.name} circuit breaker is open")
                    continue

            # Check provider health
            if provider.is_healthy():
                healthy.append(provider)
            else:
                logger.debug(f"Provider {provider.name} is not healthy: {provider.status}")

        return healthy

    def select_provider(self, request: CompletionRequest) -> BaseProvider | None:
        """Select best provider based on strategy."""
        healthy_providers = self.get_healthy_providers()

        if not healthy_providers:
            logger.error("No healthy providers available")
            return None

        # Filter providers that support the requested model
        compatible_providers = [p for p in healthy_providers if p.supports_model(request.model)]

        if not compatible_providers:
            logger.warning(
                f"No providers support model {request.model}, using any healthy provider"
            )
            compatible_providers = healthy_providers

        if len(compatible_providers) == 1:
            return compatible_providers[0]

        # Apply load balancing strategy
        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._round_robin_selection(compatible_providers)

        elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_selection(compatible_providers)

        elif self.strategy == LoadBalancingStrategy.LEAST_LATENCY:
            return self._least_latency_selection(compatible_providers)

        elif self.strategy == LoadBalancingStrategy.LEAST_LOADED:
            return self._least_loaded_selection(compatible_providers)

        elif self.strategy == LoadBalancingStrategy.RANDOM:
            return random.choice(compatible_providers)

        else:
            logger.warning(f"Unknown strategy {self.strategy}, using round robin")
            return self._round_robin_selection(compatible_providers)

    def _round_robin_selection(self, providers: list[BaseProvider]) -> BaseProvider:
        """Simple round robin selection."""
        provider = providers[self._round_robin_index % len(providers)]
        self._round_robin_index += 1
        return provider

    def _weighted_round_robin_selection(self, providers: list[BaseProvider]) -> BaseProvider:
        """Weighted round robin based on success rate."""
        weights = []

        for provider in providers:
            # Weight based on success rate and inverse of latency
            success_rate = provider.metrics.success_rate
            avg_latency = max(provider.metrics.average_latency, 1)  # Avoid division by zero

            # Higher success rate and lower latency = higher weight
            weight = success_rate / (avg_latency / 1000)  # Convert ms to seconds
            weights.append(max(weight, 0.1))  # Minimum weight to ensure all providers have a chance

        # Weighted random selection
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(providers)

        rand = random.uniform(0, total_weight)
        cumulative = 0

        for i, weight in enumerate(weights):
            cumulative += weight
            if rand <= cumulative:
                return providers[i]

        return providers[-1]  # Fallback

    def _least_latency_selection(self, providers: list[BaseProvider]) -> BaseProvider:
        """Select provider with lowest average latency."""
        return min(providers, key=lambda p: p.metrics.average_latency or float("inf"))

    def _least_loaded_selection(self, providers: list[BaseProvider]) -> BaseProvider:
        """Select provider with least current load (concurrent requests)."""
        # Use semaphore count as a proxy for current load
        return min(providers, key=lambda p: p._semaphore._value)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Complete request with failover support."""
        self.total_requests += 1
        last_error = None

        # Track which providers we've tried to avoid infinite loops
        attempted_providers = set()

        for attempt in range(self.max_retries + 1):
            provider = self.select_provider(request)

            if not provider:
                raise ProviderError(
                    "No available providers for request", error_code="no_providers", retryable=False
                )

            # Skip if we've already tried this provider
            if provider.name in attempted_providers and attempt > 0:
                # Try to find a different provider
                healthy = self.get_healthy_providers()
                available = [p for p in healthy if p.name not in attempted_providers]
                if available:
                    provider = random.choice(available)
                else:
                    # All providers tried, break out of retry loop
                    break

            attempted_providers.add(provider.name)

            try:
                logger.debug(
                    f"Attempting request with provider {provider.name} (attempt {attempt + 1})"
                )

                # Use circuit breaker if enabled
                if self.enable_circuit_breaker:
                    circuit_breaker = self.circuit_breakers[provider.name]
                    response = await circuit_breaker.call(provider.complete, request)
                else:
                    response = await provider.complete(request)

                self.successful_requests += 1
                if attempt > 0:
                    self.failover_count += 1
                    logger.info(
                        f"Request succeeded after {attempt} failovers using {provider.name}"
                    )

                return response

            except RateLimitError as e:
                logger.warning(f"Rate limit hit on {provider.name}: {e.message}")
                last_error = e

                # If provider suggests retry_after, wait briefly
                if hasattr(e, "retry_after") and e.retry_after:
                    wait_time = min(e.retry_after, 5)  # Cap at 5 seconds
                    logger.info(f"Waiting {wait_time}s before retry due to rate limit")
                    await asyncio.sleep(wait_time)

            except ProviderError as e:
                logger.warning(f"Provider {provider.name} failed: {e.message}")
                last_error = e

                # Don't retry non-retryable errors with the same provider
                if not e.retryable:
                    logger.debug(
                        f"Error is not retryable, marking provider {provider.name} as failed"
                    )

            except Exception as e:
                logger.error(f"Unexpected error from provider {provider.name}: {str(e)}")
                last_error = ProviderError(
                    f"Unexpected provider error: {str(e)}",
                    error_code="unexpected_error",
                    provider_name=provider.name,
                )

            # Brief delay before retry to avoid overwhelming providers
            if attempt < self.max_retries:
                await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff

        # All providers failed
        self.failed_requests += 1

        if last_error:
            raise last_error
        else:
            raise ProviderError(
                f"All providers failed after {self.max_retries + 1} attempts",
                error_code="all_providers_failed",
                retryable=False,
            )

    async def complete_stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Complete streaming request with failover support."""
        self.total_requests += 1
        last_error = None

        for attempt in range(self.max_retries + 1):
            provider = self.select_provider(request)

            if not provider:
                raise ProviderError(
                    "No available providers for streaming request",
                    error_code="no_providers",
                    retryable=False,
                )

            try:
                logger.debug(f"Attempting streaming request with provider {provider.name}")

                # Use circuit breaker if enabled
                if self.enable_circuit_breaker:
                    circuit_breaker = self.circuit_breakers[provider.name]
                    stream = await circuit_breaker.call(provider.complete_stream, request)
                else:
                    stream = provider.complete_stream(request)

                chunk_count = 0
                async for chunk in stream:
                    chunk_count += 1
                    yield chunk

                self.successful_requests += 1
                if attempt > 0:
                    self.failover_count += 1
                    logger.info(
                        f"Streaming request succeeded after {attempt} failovers using {provider.name}"
                    )

                return

            except Exception as e:
                logger.warning(f"Streaming failed on provider {provider.name}: {str(e)}")
                last_error = e

                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        # All providers failed
        self.failed_requests += 1

        if last_error:
            if isinstance(last_error, ProviderError):
                raise last_error
            else:
                raise ProviderError(
                    f"Streaming failed: {str(last_error)}",
                    error_code="streaming_failed",
                    retryable=False,
                )
        else:
            raise ProviderError(
                f"All providers failed for streaming after {self.max_retries + 1} attempts",
                error_code="all_providers_failed",
                retryable=False,
            )

    async def health_check(self) -> dict:
        """Get orchestrator and provider health status."""
        provider_health = {}

        for name, provider in self.providers.items():
            health_data = await provider.health_check()

            # Add circuit breaker state
            if self.enable_circuit_breaker:
                circuit_breaker = self.circuit_breakers[name]
                health_data["circuit_breaker"] = {
                    "state": circuit_breaker.state,
                    "failure_count": circuit_breaker.failure_count,
                    "last_failure_time": circuit_breaker.last_failure_time,
                }

            provider_health[name] = health_data

        # Overall orchestrator metrics
        success_rate = self.successful_requests / max(self.total_requests, 1)

        return {
            "orchestrator": {
                "strategy": self.strategy,
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "success_rate": round(success_rate, 3),
                "failover_count": self.failover_count,
                "available_providers": len(self.get_healthy_providers()),
                "total_providers": len(self.providers),
            },
            "providers": provider_health,
        }

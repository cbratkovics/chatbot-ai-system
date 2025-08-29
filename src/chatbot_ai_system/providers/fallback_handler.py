"""Fallback handler for automatic failover between providers."""

import asyncio
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class FallbackHandler:
    """Handles automatic failover between model providers."""

    def __init__(
        self,
        primary: Any,
        secondary: Any,
        retry_count: int = 3,
        circuit_breaker_threshold: int = 5,
        circuit_reset_timeout: int = 60,
        metrics_collector: Any | None = None,
    ):
        """Initialize fallback handler.

        Args:
            primary: Primary provider
            secondary: Secondary provider
            retry_count: Number of retries
            circuit_breaker_threshold: Failures before opening circuit
            circuit_reset_timeout: Circuit reset timeout in seconds
            metrics_collector: Metrics collector instance
        """
        self.primary = primary
        self.secondary = secondary
        self.retry_count = retry_count
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_reset_timeout = circuit_reset_timeout
        self.metrics_collector = metrics_collector

        self.circuit_open = False
        self.circuit_open_time = None
        self.failure_count = 0
        self.total_requests = 0
        self.fallback_count = 0

    async def execute_with_fallback(self, request: dict[str, Any]) -> dict[str, Any]:
        """Execute request with fallback logic.

        Args:
            request: Chat request

        Returns:
            Response from primary or secondary provider
        """
        self.total_requests += 1

        if not self._is_circuit_open():
            try:
                response = await self._try_primary(request)
                self._reset_circuit()
                return response
            except Exception as e:
                logger.warning(f"Primary provider failed: {e}")
                self._record_failure()

        logger.info("Falling back to secondary provider")
        self.fallback_count += 1

        if self.metrics_collector:
            self.metrics_collector.increment_counter("fallback_triggered")

        try:
            response = await self.secondary.chat_completion(request)
            # response["fallback"] = True
            return response
        except Exception as e:
            logger.error(f"Secondary provider also failed: {e}")
            raise

    async def _try_primary(self, request: dict[str, Any]) -> dict[str, Any]:
        """Try primary provider with retries.

        Args:
            request: Chat request

        Returns:
            Response from primary provider
        """
        for attempt in range(self.retry_count):
            try:
                return await self.primary.chat_completion(request)
            except Exception:
                if attempt == self.retry_count - 1:
                    raise

                wait_time = 2**attempt
                logger.warning(f"Retry {attempt + 1}/{self.retry_count} after {wait_time}s")
                await asyncio.sleep(wait_time)

    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open.

        Returns:
            True if circuit is open
        """
        if not self.circuit_open:
            return False

        if self.circuit_open_time:
            elapsed = (datetime.utcnow() - self.circuit_open_time).total_seconds()
            if elapsed > self.circuit_reset_timeout:
                logger.info("Circuit breaker reset")
                self._reset_circuit()
                return False

        return True

    def _record_failure(self):
        """Record provider failure."""
        self.failure_count += 1

        if self.failure_count >= self.circuit_breaker_threshold:
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            self.circuit_open = True
            self.circuit_open_time = datetime.utcnow()

            if self.metrics_collector:
                self.metrics_collector.increment_counter("circuit_breaker_opened")

    def _reset_circuit(self):
        """Reset circuit breaker."""
        self.circuit_open = False
        self.circuit_open_time = None
        self.failure_count = 0

        if self.metrics_collector:
            self.metrics_collector.increment_counter("circuit_breaker_reset")

    async def get_healthy_provider(self) -> Any:
        """Get currently healthy provider.

        Returns:
            Healthy provider instance
        """
        if not self._is_circuit_open():
            try:
                if await self.primary.health_check():
                    return self.primary
            except Exception:
                pass

        try:
            if await self.secondary.health_check():
                return self.secondary
        except Exception:
            pass

        return None

    def get_statistics(self) -> dict[str, Any]:
        """Get fallback statistics.

        Returns:
            Fallback statistics
        """
        return {
            "total_requests": self.total_requests,
            "fallback_count": self.fallback_count,
            "fallback_rate": self.fallback_count / self.total_requests
            if self.total_requests > 0
            else 0,
            "circuit_open": self.circuit_open,
            "failure_count": self.failure_count,
            "circuit_breaker_threshold": self.circuit_breaker_threshold,
        }

    async def test_failover(self) -> dict[str, Any]:
        """Test failover mechanism.

        Returns:
            Test results
        """
        test_request = {"message": "Test failover", "model": "gpt-3.5-turbo", "max_tokens": 10}

        results = {"primary_health": False, "secondary_health": False, "failover_successful": False}

        try:
            await self.primary.chat_completion(test_request)
            results["primary_health"] = True
        except Exception:
            pass

        try:
            await self.secondary.chat_completion(test_request)
            results["secondary_health"] = True
        except Exception:
            pass

        if not results["primary_health"] and results["secondary_health"]:
            try:
                response = await self.execute_with_fallback(test_request)
                results["failover_successful"] = response.get("fallback", False)
            except Exception:
                pass

        return results

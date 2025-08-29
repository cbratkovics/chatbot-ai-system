"""Intelligent model router with load balancing and fallback."""

import asyncio
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RoutingStrategy(str, Enum):
    """Routing strategies for model selection."""
    
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_LATENCY = "least_latency"
    WEIGHTED = "weighted"
    COST_OPTIMIZED = "cost_optimized"
    QUALITY_OPTIMIZED = "quality_optimized"


@dataclass
class ModelMetrics:
    """Metrics for a model provider."""
    
    provider: str
    model: str
    total_requests: int = 0
    failed_requests: int = 0
    total_latency: float = 0.0
    avg_latency: float = 0.0
    success_rate: float = 1.0
    cost_per_token: float = 0.0
    quality_score: float = 1.0
    last_used: Optional[float] = None
    is_available: bool = True


class ModelRouter:
    """Intelligent router for model selection and load balancing."""
    
    def __init__(
        self,
        strategy: RoutingStrategy = RoutingStrategy.LEAST_LATENCY,
        fallback_enabled: bool = True,
    ):
        """Initialize model router."""
        self.strategy = strategy
        self.fallback_enabled = fallback_enabled
        self.metrics: Dict[str, ModelMetrics] = {}
        self.round_robin_index = 0
        self.provider_weights: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    def register_model(
        self,
        provider: str,
        model: str,
        cost_per_token: float = 0.0,
        quality_score: float = 1.0,
        weight: float = 1.0,
    ):
        """Register a model with the router."""
        key = f"{provider}:{model}"
        self.metrics[key] = ModelMetrics(
            provider=provider,
            model=model,
            cost_per_token=cost_per_token,
            quality_score=quality_score,
        )
        self.provider_weights[key] = weight
    
    async def select_model(
        self,
        excluded: Optional[List[str]] = None,
    ) -> Optional[tuple[str, str]]:
        """Select best model based on routing strategy."""
        async with self._lock:
            available_models = [
                key for key, metrics in self.metrics.items()
                if metrics.is_available and (not excluded or key not in excluded)
            ]
            
            if not available_models:
                return None
            
            if self.strategy == RoutingStrategy.ROUND_ROBIN:
                selected = self._round_robin_select(available_models)
            elif self.strategy == RoutingStrategy.RANDOM:
                selected = random.choice(available_models)
            elif self.strategy == RoutingStrategy.LEAST_LATENCY:
                selected = self._least_latency_select(available_models)
            elif self.strategy == RoutingStrategy.WEIGHTED:
                selected = self._weighted_select(available_models)
            elif self.strategy == RoutingStrategy.COST_OPTIMIZED:
                selected = self._cost_optimized_select(available_models)
            elif self.strategy == RoutingStrategy.QUALITY_OPTIMIZED:
                selected = self._quality_optimized_select(available_models)
            else:
                selected = available_models[0]
            
            provider, model = selected.split(":", 1)
            return provider, model
    
    def _round_robin_select(self, models: List[str]) -> str:
        """Select model using round-robin."""
        selected = models[self.round_robin_index % len(models)]
        self.round_robin_index += 1
        return selected
    
    def _least_latency_select(self, models: List[str]) -> str:
        """Select model with least latency."""
        return min(
            models,
            key=lambda m: self.metrics[m].avg_latency if self.metrics[m].total_requests > 0 else 0,
        )
    
    def _weighted_select(self, models: List[str]) -> str:
        """Select model using weighted random."""
        weights = [self.provider_weights.get(m, 1.0) for m in models]
        return random.choices(models, weights=weights)[0]
    
    def _cost_optimized_select(self, models: List[str]) -> str:
        """Select most cost-effective model."""
        return min(models, key=lambda m: self.metrics[m].cost_per_token)
    
    def _quality_optimized_select(self, models: List[str]) -> str:
        """Select highest quality model."""
        return max(models, key=lambda m: self.metrics[m].quality_score)
    
    async def record_success(
        self,
        provider: str,
        model: str,
        latency: float,
    ):
        """Record successful request."""
        async with self._lock:
            key = f"{provider}:{model}"
            if key in self.metrics:
                metrics = self.metrics[key]
                metrics.total_requests += 1
                metrics.total_latency += latency
                metrics.avg_latency = metrics.total_latency / metrics.total_requests
                metrics.success_rate = (
                    (metrics.total_requests - metrics.failed_requests)
                    / metrics.total_requests
                )
                metrics.last_used = time.time()
    
    async def record_failure(
        self,
        provider: str,
        model: str,
    ):
        """Record failed request."""
        async with self._lock:
            key = f"{provider}:{model}"
            if key in self.metrics:
                metrics = self.metrics[key]
                metrics.total_requests += 1
                metrics.failed_requests += 1
                metrics.success_rate = (
                    (metrics.total_requests - metrics.failed_requests)
                    / metrics.total_requests
                )
                
                # Mark as unavailable if failure rate is too high
                if metrics.success_rate < 0.5 and metrics.total_requests > 10:
                    metrics.is_available = False
    
    async def mark_unavailable(self, provider: str, model: str):
        """Mark model as unavailable."""
        async with self._lock:
            key = f"{provider}:{model}"
            if key in self.metrics:
                self.metrics[key].is_available = False
    
    async def mark_available(self, provider: str, model: str):
        """Mark model as available."""
        async with self._lock:
            key = f"{provider}:{model}"
            if key in self.metrics:
                self.metrics[key].is_available = True
    
    def get_metrics(self) -> Dict[str, ModelMetrics]:
        """Get current metrics for all models."""
        return self.metrics.copy()
    
    def reset_metrics(self):
        """Reset all metrics."""
        for metrics in self.metrics.values():
            metrics.total_requests = 0
            metrics.failed_requests = 0
            metrics.total_latency = 0.0
            metrics.avg_latency = 0.0
            metrics.success_rate = 1.0
            metrics.is_available = True
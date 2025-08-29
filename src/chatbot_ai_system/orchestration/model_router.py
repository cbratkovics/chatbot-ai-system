"""Advanced model router with intelligent selection using Strategy pattern."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks for model selection."""

    CHAT = "chat"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    CREATIVE_WRITING = "creative_writing"
    ANALYSIS = "analysis"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    QA = "question_answering"
    REASONING = "reasoning"
    VISION = "vision"


class ModelCapability(Enum):
    """Model capabilities."""

    TEXT_GENERATION = "text_generation"
    CODE = "code"
    FUNCTION_CALLING = "function_calling"
    VISION = "vision"
    LONG_CONTEXT = "long_context"
    STREAMING = "streaming"
    JSON_MODE = "json_mode"


@dataclass
class ModelProfile:
    """Profile of a model with capabilities and metrics."""

    provider: str
    model: str
    capabilities: list[ModelCapability]
    max_tokens: int
    cost_per_1k_input: float
    cost_per_1k_output: float
    avg_latency_ms: float
    quality_score: float  # 0-1 scale
    context_window: int
    tier_access: list[str]  # Tenant tiers that can access


@dataclass
class RoutingContext:
    """Context for routing decision."""

    query: str
    task_type: TaskType | None
    token_count: int
    tenant_id: str | None
    tenant_tier: str
    required_capabilities: list[ModelCapability]
    max_cost: float | None
    max_latency_ms: float | None
    preferred_models: list[str]
    excluded_models: list[str]
    temperature: float
    max_tokens: int
    metadata: dict[str, Any]


@dataclass
class RoutingDecision:
    """Routing decision with reasoning."""

    primary_model: str
    primary_provider: str
    fallback_models: list[tuple[str, str]]  # [(provider, model)]
    strategy_used: str
    score: float
    estimated_cost: float
    estimated_latency_ms: float
    reasoning: str


class RoutingStrategy(ABC):
    """Abstract base class for routing strategies."""

    @abstractmethod
    async def select_model(
        self, context: RoutingContext, available_models: list[ModelProfile]
    ) -> RoutingDecision:
        """Select model based on strategy.

        Args:
            context: Routing context
            available_models: Available model profiles

        Returns:
            Routing decision
        """
        pass


class CostOptimizedStrategy(RoutingStrategy):
    """Select cheapest model that meets requirements."""

    async def select_model(
        self, context: RoutingContext, available_models: list[ModelProfile]
    ) -> RoutingDecision:
        """Select most cost-effective model."""
        # Filter models by requirements
        eligible_models = self._filter_eligible_models(context, available_models)

        if not eligible_models:
            raise ValueError("No eligible models found")

        # Calculate cost for each model
        model_costs = []
        for model in eligible_models:
            estimated_cost = self._calculate_cost(model, context)
            model_costs.append((model, estimated_cost))

        # Sort by cost
        model_costs.sort(key=lambda x: x[1])

        # Select cheapest
        selected_model = model_costs[0][0]
        selected_cost = model_costs[0][1]

        # Get fallbacks (next 2 cheapest)
        fallbacks = [(m.provider, m.model) for m, _ in model_costs[1:3]]

        return RoutingDecision(
            primary_model=selected_model.model,
            primary_provider=selected_model.provider,
            fallback_models=fallbacks,
            strategy_used="cost_optimized",
            score=1.0 / (1 + selected_cost),  # Inverse cost as score
            estimated_cost=selected_cost,
            estimated_latency_ms=selected_model.avg_latency_ms,
            reasoning=f"Selected {selected_model.model} as most cost-effective at ${selected_cost:.4f}",
        )

    def _filter_eligible_models(
        self, context: RoutingContext, models: list[ModelProfile]
    ) -> list[ModelProfile]:
        """Filter models based on requirements."""
        eligible = []

        for model in models:
            # Check tier access
            if context.tenant_tier not in model.tier_access:
                continue

            # Check capabilities
            if not all(cap in model.capabilities for cap in context.required_capabilities):
                continue

            # Check context window
            if context.token_count > model.context_window:
                continue

            # Check exclusions
            if model.model in context.excluded_models:
                continue

            # Check max cost if specified
            if context.max_cost:
                est_cost = self._calculate_cost(model, context)
                if est_cost > context.max_cost:
                    continue

            eligible.append(model)

        return eligible

    def _calculate_cost(self, model: ModelProfile, context: RoutingContext) -> float:
        """Calculate estimated cost."""
        input_cost = (context.token_count / 1000) * model.cost_per_1k_input
        output_cost = (context.max_tokens / 1000) * model.cost_per_1k_output
        return input_cost + output_cost


class PerformanceOptimizedStrategy(RoutingStrategy):
    """Select highest quality model within constraints."""

    async def select_model(
        self, context: RoutingContext, available_models: list[ModelProfile]
    ) -> RoutingDecision:
        """Select highest performance model."""
        # Filter eligible models
        eligible_models = self._filter_by_constraints(context, available_models)

        if not eligible_models:
            raise ValueError("No eligible models found")

        # Score models by performance
        model_scores = []
        for model in eligible_models:
            score = self._calculate_performance_score(model, context)
            model_scores.append((model, score))

        # Sort by score (highest first)
        model_scores.sort(key=lambda x: x[1], reverse=True)

        # Select best
        selected_model = model_scores[0][0]
        selected_score = model_scores[0][1]

        # Get fallbacks
        fallbacks = [(m.provider, m.model) for m, _ in model_scores[1:3]]

        return RoutingDecision(
            primary_model=selected_model.model,
            primary_provider=selected_model.provider,
            fallback_models=fallbacks,
            strategy_used="performance_optimized",
            score=selected_score,
            estimated_cost=self._calculate_cost(selected_model, context),
            estimated_latency_ms=selected_model.avg_latency_ms,
            reasoning=f"Selected {selected_model.model} for highest quality with score {selected_score:.2f}",
        )

    def _filter_by_constraints(
        self, context: RoutingContext, models: list[ModelProfile]
    ) -> list[ModelProfile]:
        """Filter models by constraints."""
        eligible = []

        for model in models:
            # Basic eligibility checks
            if context.tenant_tier not in model.tier_access:
                continue

            if context.token_count > model.context_window:
                continue

            if model.model in context.excluded_models:
                continue

            # Latency constraint
            if context.max_latency_ms and model.avg_latency_ms > context.max_latency_ms:
                continue

            eligible.append(model)

        return eligible

    def _calculate_performance_score(self, model: ModelProfile, context: RoutingContext) -> float:
        """Calculate performance score."""
        # Base quality score
        score = model.quality_score

        # Boost for specific task types
        task_boosts = {
            TaskType.CODE_GENERATION: {"gpt-4": 0.2, "claude-3-opus": 0.25},
            TaskType.CREATIVE_WRITING: {"gpt-4": 0.15, "claude-3-opus": 0.2},
            TaskType.REASONING: {"gpt-4": 0.2, "claude-3-opus": 0.15},
            TaskType.VISION: {"gpt-4-vision": 0.3},
        }

        if context.task_type and context.task_type in task_boosts:
            if model.model in task_boosts[context.task_type]:
                score += task_boosts[context.task_type][model.model]

        # Penalty for high latency
        latency_penalty = min(0.2, model.avg_latency_ms / 10000)
        score -= latency_penalty

        return max(0, min(1, score))

    def _calculate_cost(self, model: ModelProfile, context: RoutingContext) -> float:
        """Calculate estimated cost."""
        input_cost = (context.token_count / 1000) * model.cost_per_1k_input
        output_cost = (context.max_tokens / 1000) * model.cost_per_1k_output
        return input_cost + output_cost


class CapabilityBasedStrategy(RoutingStrategy):
    """Select model based on required capabilities."""

    async def select_model(
        self, context: RoutingContext, available_models: list[ModelProfile]
    ) -> RoutingDecision:
        """Select model based on capabilities."""
        # Filter by required capabilities
        capable_models = [
            m
            for m in available_models
            if all(cap in m.capabilities for cap in context.required_capabilities)
            and context.tenant_tier in m.tier_access
        ]

        if not capable_models:
            raise ValueError(
                f"No models with required capabilities: {context.required_capabilities}"
            )

        # Score by capability match and quality
        model_scores = []
        for model in capable_models:
            score = self._calculate_capability_score(model, context)
            model_scores.append((model, score))

        # Sort by score
        model_scores.sort(key=lambda x: x[1], reverse=True)

        selected_model = model_scores[0][0]
        selected_score = model_scores[0][1]

        fallbacks = [(m.provider, m.model) for m, _ in model_scores[1:3]]

        return RoutingDecision(
            primary_model=selected_model.model,
            primary_provider=selected_model.provider,
            fallback_models=fallbacks,
            strategy_used="capability_based",
            score=selected_score,
            estimated_cost=self._calculate_cost(selected_model, context),
            estimated_latency_ms=selected_model.avg_latency_ms,
            reasoning=f"Selected {selected_model.model} for best capability match",
        )

    def _calculate_capability_score(self, model: ModelProfile, context: RoutingContext) -> float:
        """Calculate capability match score."""
        # Base score from quality
        score = model.quality_score * 0.5

        # Capability match bonus
        capability_match = len(set(model.capabilities) & set(context.required_capabilities))
        capability_bonus = capability_match * 0.1
        score += capability_bonus

        # Context window fitness
        if context.token_count < model.context_window * 0.5:
            score += 0.1  # Not over-provisioned

        # Task-specific bonuses
        task_capability_map = {
            TaskType.CODE_GENERATION: ModelCapability.CODE,
            TaskType.VISION: ModelCapability.VISION,
            TaskType.QA: ModelCapability.LONG_CONTEXT,
        }

        if context.task_type and context.task_type in task_capability_map:
            required_cap = task_capability_map[context.task_type]
            if required_cap in model.capabilities:
                score += 0.2

        return min(1.0, score)

    def _calculate_cost(self, model: ModelProfile, context: RoutingContext) -> float:
        """Calculate estimated cost."""
        input_cost = (context.token_count / 1000) * model.cost_per_1k_input
        output_cost = (context.max_tokens / 1000) * model.cost_per_1k_output
        return input_cost + output_cost


class AdaptiveStrategy(RoutingStrategy):
    """Adaptive strategy that learns from historical performance."""

    def __init__(self):
        self.performance_history = {}
        self.cost_history = {}

    async def select_model(
        self, context: RoutingContext, available_models: list[ModelProfile]
    ) -> RoutingDecision:
        """Select model based on historical performance."""
        # Filter eligible models
        eligible_models = self._filter_eligible(context, available_models)

        if not eligible_models:
            raise ValueError("No eligible models found")

        # Score models based on historical data
        model_scores = []
        for model in eligible_models:
            score = self._calculate_adaptive_score(model, context)
            model_scores.append((model, score))

        # Sort by score
        model_scores.sort(key=lambda x: x[1], reverse=True)

        selected_model = model_scores[0][0]
        selected_score = model_scores[0][1]

        fallbacks = [(m.provider, m.model) for m, _ in model_scores[1:3]]

        return RoutingDecision(
            primary_model=selected_model.model,
            primary_provider=selected_model.provider,
            fallback_models=fallbacks,
            strategy_used="adaptive",
            score=selected_score,
            estimated_cost=self._estimate_cost(selected_model, context),
            estimated_latency_ms=self._estimate_latency(selected_model, context),
            reasoning=f"Selected {selected_model.model} based on historical performance",
        )

    def _filter_eligible(
        self, context: RoutingContext, models: list[ModelProfile]
    ) -> list[ModelProfile]:
        """Filter eligible models."""
        return [
            m
            for m in models
            if context.tenant_tier in m.tier_access
            and context.token_count <= m.context_window
            and m.model not in context.excluded_models
        ]

    def _calculate_adaptive_score(self, model: ModelProfile, context: RoutingContext) -> float:
        """Calculate score based on historical data."""
        model_key = f"{model.provider}:{model.model}"

        # Get historical performance
        if model_key in self.performance_history:
            hist_performance = self.performance_history[model_key]
            performance_score = hist_performance.get("success_rate", 0.5)
        else:
            performance_score = model.quality_score

        # Get historical cost efficiency
        if model_key in self.cost_history:
            hist_cost = self.cost_history[model_key]
            cost_efficiency = 1.0 / (1 + hist_cost.get("avg_cost", 0.1))
        else:
            est_cost = self._estimate_cost(model, context)
            cost_efficiency = 1.0 / (1 + est_cost)

        # Combine scores
        score = (performance_score * 0.6) + (cost_efficiency * 0.4)

        # Apply recency bias
        if model_key in self.performance_history:
            last_used = self.performance_history[model_key].get("last_used")
            if last_used:
                age_hours = (datetime.utcnow() - last_used).total_seconds() / 3600
                recency_factor = 1.0 / (1 + age_hours / 24)  # Decay over 24 hours
                score *= 0.8 + 0.2 * recency_factor

        return score

    def _estimate_cost(self, model: ModelProfile, context: RoutingContext) -> float:
        """Estimate cost."""
        input_cost = (context.token_count / 1000) * model.cost_per_1k_input
        output_cost = (context.max_tokens / 1000) * model.cost_per_1k_output
        return input_cost + output_cost

    def _estimate_latency(self, model: ModelProfile, context: RoutingContext) -> float:
        """Estimate latency."""
        model_key = f"{model.provider}:{model.model}"

        if model_key in self.performance_history:
            return self.performance_history[model_key].get("avg_latency_ms", model.avg_latency_ms)

        return model.avg_latency_ms

    async def update_history(
        self, provider: str, model: str, success: bool, latency_ms: float, cost: float
    ):
        """Update historical data.

        Args:
            provider: Provider name
            model: Model name
            success: Whether request succeeded
            latency_ms: Actual latency
            cost: Actual cost
        """
        model_key = f"{provider}:{model}"

        # Update performance history
        if model_key not in self.performance_history:
            self.performance_history[model_key] = {
                "success_count": 0,
                "total_count": 0,
                "avg_latency_ms": 0,
                "last_used": None,
            }

        hist = self.performance_history[model_key]
        hist["total_count"] += 1
        if success:
            hist["success_count"] += 1
        hist["success_rate"] = hist["success_count"] / hist["total_count"]

        # Update rolling average latency
        alpha = 0.1  # Exponential moving average factor
        hist["avg_latency_ms"] = (1 - alpha) * hist["avg_latency_ms"] + alpha * latency_ms
        hist["last_used"] = datetime.utcnow()

        # Update cost history
        if model_key not in self.cost_history:
            self.cost_history[model_key] = {"total_cost": 0, "request_count": 0, "avg_cost": 0}

        cost_hist = self.cost_history[model_key]
        cost_hist["total_cost"] += cost
        cost_hist["request_count"] += 1
        cost_hist["avg_cost"] = cost_hist["total_cost"] / cost_hist["request_count"]


class ModelRouter:
    """Main model router that orchestrates selection strategies."""

    def __init__(self):
        """Initialize model router."""
        self.strategies = {
            "cost_optimized": CostOptimizedStrategy(),
            "performance_optimized": PerformanceOptimizedStrategy(),
            "capability_based": CapabilityBasedStrategy(),
            "adaptive": AdaptiveStrategy(),
        }

        self.model_profiles = self._load_model_profiles()
        self.routing_history = []

    def _load_model_profiles(self) -> list[ModelProfile]:
        """Load model profiles."""
        return [
            # OpenAI Models
            ModelProfile(
                provider="openai",
                model="gpt-3.5-turbo",
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.FUNCTION_CALLING,
                    ModelCapability.JSON_MODE,
                    ModelCapability.STREAMING,
                ],
                max_tokens=4096,
                cost_per_1k_input=0.0005,
                cost_per_1k_output=0.0015,
                avg_latency_ms=800,
                quality_score=0.7,
                context_window=16385,
                tier_access=["basic", "professional", "enterprise"],
            ),
            ModelProfile(
                provider="openai",
                model="gpt-4",
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE,
                    ModelCapability.FUNCTION_CALLING,
                    ModelCapability.JSON_MODE,
                    ModelCapability.STREAMING,
                ],
                max_tokens=8192,
                cost_per_1k_input=0.03,
                cost_per_1k_output=0.06,
                avg_latency_ms=2000,
                quality_score=0.9,
                context_window=8192,
                tier_access=["professional", "enterprise"],
            ),
            ModelProfile(
                provider="openai",
                model="gpt-4-turbo",
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE,
                    ModelCapability.FUNCTION_CALLING,
                    ModelCapability.VISION,
                    ModelCapability.JSON_MODE,
                    ModelCapability.STREAMING,
                    ModelCapability.LONG_CONTEXT,
                ],
                max_tokens=4096,
                cost_per_1k_input=0.01,
                cost_per_1k_output=0.03,
                avg_latency_ms=1500,
                quality_score=0.95,
                context_window=128000,
                tier_access=["enterprise"],
            ),
            # Anthropic Models
            ModelProfile(
                provider="anthropic",
                model="claude-3-sonnet",
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE,
                    ModelCapability.STREAMING,
                    ModelCapability.LONG_CONTEXT,
                ],
                max_tokens=4096,
                cost_per_1k_input=0.003,
                cost_per_1k_output=0.015,
                avg_latency_ms=1200,
                quality_score=0.85,
                context_window=200000,
                tier_access=["professional", "enterprise"],
            ),
            ModelProfile(
                provider="anthropic",
                model="claude-3-opus",
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE,
                    ModelCapability.STREAMING,
                    ModelCapability.LONG_CONTEXT,
                    ModelCapability.VISION,
                ],
                max_tokens=4096,
                cost_per_1k_input=0.015,
                cost_per_1k_output=0.075,
                avg_latency_ms=2500,
                quality_score=0.98,
                context_window=200000,
                tier_access=["enterprise"],
            ),
            # Llama Models
            ModelProfile(
                provider="llama",
                model="llama-3-8b",
                capabilities=[ModelCapability.TEXT_GENERATION, ModelCapability.STREAMING],
                max_tokens=2048,
                cost_per_1k_input=0.0001,
                cost_per_1k_output=0.0002,
                avg_latency_ms=400,
                quality_score=0.65,
                context_window=8192,
                tier_access=["basic", "professional", "enterprise"],
            ),
            ModelProfile(
                provider="llama",
                model="llama-3-70b",
                capabilities=[
                    ModelCapability.TEXT_GENERATION,
                    ModelCapability.CODE,
                    ModelCapability.STREAMING,
                ],
                max_tokens=4096,
                cost_per_1k_input=0.0005,
                cost_per_1k_output=0.001,
                avg_latency_ms=1000,
                quality_score=0.8,
                context_window=8192,
                tier_access=["professional", "enterprise"],
            ),
        ]

    async def route(
        self,
        query: str,
        tenant_id: str | None = None,
        tenant_tier: str = "basic",
        strategy: str | None = None,
        **kwargs,
    ) -> RoutingDecision:
        """Route query to appropriate model.

        Args:
            query: User query
            tenant_id: Tenant identifier
            tenant_tier: Tenant tier
            strategy: Routing strategy to use
            **kwargs: Additional routing parameters

        Returns:
            Routing decision
        """
        # Detect task type
        task_type = self._detect_task_type(query)

        # Count tokens
        token_count = self._estimate_tokens(query)

        # Determine required capabilities
        required_capabilities = self._determine_capabilities(query, task_type)

        # Create routing context
        context = RoutingContext(
            query=query,
            task_type=task_type,
            token_count=token_count,
            tenant_id=tenant_id,
            tenant_tier=tenant_tier,
            required_capabilities=required_capabilities,
            max_cost=kwargs.get("max_cost"),
            max_latency_ms=kwargs.get("max_latency_ms"),
            preferred_models=kwargs.get("preferred_models", []),
            excluded_models=kwargs.get("excluded_models", []),
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 1000),
            metadata=kwargs.get("metadata", {}),
        )

        # Select strategy
        if not strategy:
            strategy = self._select_strategy(context)

        if strategy not in self.strategies:
            strategy = "cost_optimized"

        # Route using selected strategy
        routing_strategy = self.strategies[strategy]
        decision = await routing_strategy.select_model(context, self.model_profiles)

        # Record routing decision
        self._record_routing(context, decision)

        return decision

    def _detect_task_type(self, query: str) -> TaskType:
        """Detect task type from query.

        Args:
            query: User query

        Returns:
            Detected task type
        """
        query_lower = query.lower()

        # Simple keyword-based detection
        if any(kw in query_lower for kw in ["code", "function", "class", "debug", "fix"]):
            return TaskType.CODE_GENERATION
        elif any(kw in query_lower for kw in ["review", "improve", "optimize"]):
            return TaskType.CODE_REVIEW
        elif any(kw in query_lower for kw in ["story", "poem", "creative", "write"]):
            return TaskType.CREATIVE_WRITING
        elif any(kw in query_lower for kw in ["analyze", "explain", "compare"]):
            return TaskType.ANALYSIS
        elif any(kw in query_lower for kw in ["translate", "translation"]):
            return TaskType.TRANSLATION
        elif any(kw in query_lower for kw in ["summarize", "summary", "brief"]):
            return TaskType.SUMMARIZATION
        elif any(kw in query_lower for kw in ["why", "what", "how", "when", "where"]):
            return TaskType.QA
        elif any(kw in query_lower for kw in ["reason", "logic", "deduce", "infer"]):
            return TaskType.REASONING
        elif any(kw in query_lower for kw in ["image", "picture", "photo", "visual"]):
            return TaskType.VISION
        else:
            return TaskType.CHAT

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        # Simple estimation: ~4 characters per token
        return len(text) // 4

    def _determine_capabilities(self, query: str, task_type: TaskType) -> list[ModelCapability]:
        """Determine required capabilities.

        Args:
            query: User query
            task_type: Task type

        Returns:
            Required capabilities
        """
        capabilities = [ModelCapability.TEXT_GENERATION]

        if task_type in [TaskType.CODE_GENERATION, TaskType.CODE_REVIEW]:
            capabilities.append(ModelCapability.CODE)

        if task_type == TaskType.VISION:
            capabilities.append(ModelCapability.VISION)

        # Check for long context needs
        if self._estimate_tokens(query) > 4000:
            capabilities.append(ModelCapability.LONG_CONTEXT)

        return capabilities

    def _select_strategy(self, context: RoutingContext) -> str:
        """Select routing strategy based on context.

        Args:
            context: Routing context

        Returns:
            Strategy name
        """
        # Use adaptive if we have history
        if len(self.routing_history) > 100:
            return "adaptive"

        # Use capability-based for specific requirements
        if len(context.required_capabilities) > 2:
            return "capability_based"

        # Use performance for complex tasks
        if context.task_type in [
            TaskType.CODE_GENERATION,
            TaskType.REASONING,
            TaskType.CREATIVE_WRITING,
        ]:
            return "performance_optimized"

        # Default to cost optimization
        return "cost_optimized"

    def _record_routing(self, context: RoutingContext, decision: RoutingDecision):
        """Record routing decision for analysis.

        Args:
            context: Routing context
            decision: Routing decision
        """
        self.routing_history.append(
            {
                "timestamp": datetime.utcnow(),
                "tenant_id": context.tenant_id,
                "task_type": context.task_type.value if context.task_type else None,
                "model_selected": decision.primary_model,
                "provider": decision.primary_provider,
                "strategy": decision.strategy_used,
                "estimated_cost": decision.estimated_cost,
                "estimated_latency": decision.estimated_latency_ms,
            }
        )

        # Keep only recent history
        if len(self.routing_history) > 10000:
            self.routing_history = self.routing_history[-5000:]

    async def update_model_performance(
        self, provider: str, model: str, success: bool, actual_latency_ms: float, actual_cost: float
    ):
        """Update model performance metrics.

        Args:
            provider: Provider name
            model: Model name
            success: Whether request succeeded
            actual_latency_ms: Actual latency
            actual_cost: Actual cost
        """
        # Update adaptive strategy history
        if "adaptive" in self.strategies:
            await self.strategies["adaptive"].update_history(
                provider, model, success, actual_latency_ms, actual_cost
            )

        # Update model profile if significant deviation
        for profile in self.model_profiles:
            if profile.provider == provider and profile.model == model:
                # Update rolling average latency
                alpha = 0.05  # Learning rate
                profile.avg_latency_ms = (
                    1 - alpha
                ) * profile.avg_latency_ms + alpha * actual_latency_ms
                break

    def get_routing_stats(self) -> dict[str, Any]:
        """Get routing statistics.

        Returns:
            Routing statistics
        """
        if not self.routing_history:
            return {}

        # Calculate statistics
        total_requests = len(self.routing_history)

        # Model usage
        model_usage = {}
        strategy_usage = {}
        total_cost = 0
        total_latency = 0

        for record in self.routing_history:
            model = record["model_selected"]
            strategy = record["strategy"]

            model_usage[model] = model_usage.get(model, 0) + 1
            strategy_usage[strategy] = strategy_usage.get(strategy, 0) + 1
            total_cost += record["estimated_cost"]
            total_latency += record["estimated_latency"]

        return {
            "total_requests": total_requests,
            "model_usage": model_usage,
            "strategy_usage": strategy_usage,
            "avg_estimated_cost": total_cost / total_requests,
            "avg_estimated_latency_ms": total_latency / total_requests,
            "cost_savings": self._calculate_cost_savings(),
        }

    def _calculate_cost_savings(self) -> float:
        """Calculate cost savings from optimal routing.

        Returns:
            Estimated savings percentage
        """
        if not self.routing_history:
            return 0.0

        # Compare to always using most expensive model
        max_cost_model = max(self.model_profiles, key=lambda m: m.cost_per_1k_output)

        actual_cost = sum(r["estimated_cost"] for r in self.routing_history)

        # Estimate cost if always used expensive model
        expensive_cost = len(self.routing_history) * (
            (1000 / 1000) * max_cost_model.cost_per_1k_input
            + (1000 / 1000) * max_cost_model.cost_per_1k_output
        )

        if expensive_cost > 0:
            savings = ((expensive_cost - actual_cost) / expensive_cost) * 100
            return max(0, savings)

        return 0.0

"""Cost tracking models."""

from datetime import datetime

from pydantic import BaseModel


class TokenUsage(BaseModel):
    """Token usage metrics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class UsageMetrics(BaseModel):
    """Usage metrics for tracking."""

    requests: int = 0
    tokens: TokenUsage
    cost: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0


class CostReport(BaseModel):
    """Cost report model."""

    tenant_id: str
    period_start: datetime
    period_end: datetime
    total_cost: float
    usage_metrics: UsageMetrics
    cost_by_model: dict[str, float] = {}
    cost_by_provider: dict[str, float] = {}

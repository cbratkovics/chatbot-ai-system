"""Real-time cost tracking for provider usage."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class CostEntry:
    """Individual cost entry."""

    timestamp: float = field(default_factory=time.time)
    tenant_id: str = ""
    user_id: str = ""
    conversation_id: str = ""

    provider: str = ""
    model: str = ""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    prompt_cost: float = 0.0
    completion_cost: float = 0.0
    total_cost: float = 0.0

    cached: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
            "provider": self.provider,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "prompt_cost": self.prompt_cost,
            "completion_cost": self.completion_cost,
            "total_cost": self.total_cost,
            "cached": self.cached,
        }


@dataclass
class CostSummary:
    """Cost summary for reporting."""

    period_start: datetime
    period_end: datetime

    total_requests: int = 0
    cached_requests: int = 0

    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    total_cost: float = 0.0
    prompt_cost: float = 0.0
    completion_cost: float = 0.0

    cost_by_provider: dict[str, float] = field(default_factory=dict)
    cost_by_model: dict[str, float] = field(default_factory=dict)
    cost_by_tenant: dict[str, float] = field(default_factory=dict)

    cache_savings: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_requests": self.total_requests,
            "cached_requests": self.cached_requests,
            "cache_hit_rate": self.cached_requests / max(self.total_requests, 1),
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_cost": round(self.total_cost, 4),
            "prompt_cost": round(self.prompt_cost, 4),
            "completion_cost": round(self.completion_cost, 4),
            "cost_by_provider": {k: round(v, 4) for k, v in self.cost_by_provider.items()},
            "cost_by_model": {k: round(v, 4) for k, v in self.cost_by_model.items()},
            "cost_by_tenant": {k: round(v, 4) for k, v in self.cost_by_tenant.items()},
            "cache_savings": round(self.cache_savings, 4),
            "average_cost_per_request": round(self.total_cost / max(self.total_requests, 1), 4),
        }


class CostTracker:
    """Tracks and manages costs across the system."""

    # Model pricing (per 1K tokens)
    MODEL_PRICING = {
        "model-4": {"prompt": 0.03, "completion": 0.06},
        "model-4-32k": {"prompt": 0.06, "completion": 0.12},
        "model-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
        "model-3.5-turbo-16k": {"prompt": 0.003, "completion": 0.004},
        "model-3-opus": {"prompt": 0.015, "completion": 0.075},
        "model-3-sonnet": {"prompt": 0.003, "completion": 0.015},
        "model-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
    }

    def __init__(self):
        self.entries: list[CostEntry] = []
        self.daily_costs: dict[str, float] = {}
        self.monthly_costs: dict[str, float] = {}

        logger.info("Cost tracker initialized")

    def track_usage(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        tenant_id: str | None = None,
        user_id: str | None = None,
        conversation_id: str | None = None,
        cached: bool = False,
    ) -> CostEntry:
        """Track provider usage and calculate costs."""

        # Calculate costs
        prompt_cost = self._calculate_cost(model, "prompt", prompt_tokens)
        completion_cost = self._calculate_cost(model, "completion", completion_tokens)
        total_cost = prompt_cost + completion_cost

        # Create cost entry
        entry = CostEntry(
            tenant_id=tenant_id or "",
            user_id=user_id or "",
            conversation_id=conversation_id or "",
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            prompt_cost=prompt_cost,
            completion_cost=completion_cost,
            total_cost=total_cost,
            cached=cached,
        )

        # Store entry
        self.entries.append(entry)

        # Update daily/monthly aggregates
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")

        self.daily_costs[today] = self.daily_costs.get(today, 0) + total_cost
        self.monthly_costs[month] = self.monthly_costs.get(month, 0) + total_cost

        logger.debug(
            f"Tracked cost: ${total_cost:.4f} for {model} ({prompt_tokens}+{completion_tokens} tokens)"
        )

        return entry

    def _calculate_cost(self, model: str, token_type: str, tokens: int) -> float:
        """Calculate cost for tokens."""
        if model not in self.MODEL_PRICING:
            # Default pricing if model not found
            return tokens * 0.002 / 1000

        price_per_1k = self.MODEL_PRICING[model].get(token_type, 0.002)
        return (tokens / 1000) * price_per_1k

    def get_summary(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        tenant_id: str | None = None,
    ) -> CostSummary:
        """Get cost summary for period."""

        # Default to last 24 hours
        if not end_time:
            end_time = datetime.now()
        if not start_time:
            start_time = end_time - timedelta(days=1)

        # Filter entries
        filtered_entries = []
        for entry in self.entries:
            entry_time = datetime.fromtimestamp(entry.timestamp)

            if entry_time < start_time or entry_time > end_time:
                continue

            if tenant_id and entry.tenant_id != tenant_id:
                continue

            filtered_entries.append(entry)

        # Calculate summary
        summary = CostSummary(period_start=start_time, period_end=end_time)

        for entry in filtered_entries:
            summary.total_requests += 1

            if entry.cached:
                summary.cached_requests += 1
                # Calculate savings from cache hit
                summary.cache_savings += entry.total_cost
            else:
                # Only count actual costs for non-cached requests
                summary.total_tokens += entry.total_tokens
                summary.prompt_tokens += entry.prompt_tokens
                summary.completion_tokens += entry.completion_tokens

                summary.total_cost += entry.total_cost
                summary.prompt_cost += entry.prompt_cost
                summary.completion_cost += entry.completion_cost

                # Aggregate by dimensions
                summary.cost_by_provider[entry.provider] = (
                    summary.cost_by_provider.get(entry.provider, 0) + entry.total_cost
                )

                summary.cost_by_model[entry.model] = (
                    summary.cost_by_model.get(entry.model, 0) + entry.total_cost
                )

                if entry.tenant_id:
                    summary.cost_by_tenant[entry.tenant_id] = (
                        summary.cost_by_tenant.get(entry.tenant_id, 0) + entry.total_cost
                    )

        return summary

    def get_tenant_usage(
        self,
        tenant_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict:
        """Get usage details for a specific tenant."""
        summary = self.get_summary(start_time, end_time, tenant_id)

        return {
            "tenant_id": tenant_id,
            "period": {
                "start": summary.period_start.isoformat(),
                "end": summary.period_end.isoformat(),
            },
            "usage": {
                "requests": summary.total_requests,
                "cached_requests": summary.cached_requests,
                "tokens": summary.total_tokens,
                "cost": round(summary.total_cost, 4),
                "savings": round(summary.cache_savings, 4),
            },
            "breakdown": {
                "by_model": summary.cost_by_model,
                "by_provider": summary.cost_by_provider,
            },
        }

    def get_cost_projection(self, days: int = 30) -> dict:
        """Project costs based on recent usage."""

        # Get last 7 days of usage
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

        summary = self.get_summary(start_time, end_time)

        # Calculate daily average
        days_actual = (end_time - start_time).days or 1
        daily_average = summary.total_cost / days_actual

        # Project forward
        projection = {
            "daily_average": round(daily_average, 2),
            "projected_cost": round(daily_average * days, 2),
            "projection_days": days,
            "based_on_days": days_actual,
            "current_month_total": round(
                self.monthly_costs.get(datetime.now().strftime("%Y-%m"), 0), 2
            ),
            "savings_from_cache": round(summary.cache_savings * (days / days_actual), 2),
        }

        return projection

    def export_costs(self, format: str = "json") -> str:
        """Export cost data."""
        if format == "json":
            import json

            data = {
                "entries": [e.to_dict() for e in self.entries],
                "daily_costs": self.daily_costs,
                "monthly_costs": self.monthly_costs,
            }
            return json.dumps(data, indent=2)

        elif format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "timestamp",
                    "tenant_id",
                    "user_id",
                    "provider",
                    "model",
                    "tokens",
                    "cost",
                    "cached",
                ],
            )

            writer.writeheader()
            for entry in self.entries:
                writer.writerow(
                    {
                        "timestamp": datetime.fromtimestamp(entry.timestamp).isoformat(),
                        "tenant_id": entry.tenant_id,
                        "user_id": entry.user_id,
                        "provider": entry.provider,
                        "model": entry.model,
                        "tokens": entry.total_tokens,
                        "cost": entry.total_cost,
                        "cached": entry.cached,
                    }
                )

            return output.getvalue()

        else:
            raise ValueError(f"Unsupported export format: {format}")


# Global cost tracker instance
cost_tracker = CostTracker()

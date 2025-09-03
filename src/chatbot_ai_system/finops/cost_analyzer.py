"""Cost analysis and optimization recommendations."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from .cost_tracker import CostTracker

logger = logging.getLogger(__name__)


@dataclass
class CostOptimization:
    """Cost optimization recommendation."""

    title: str
    description: str
    potential_savings: float
    implementation_effort: str  # low, medium, high
    priority: int  # 1-5, 1 being highest

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "potential_savings": round(self.potential_savings, 2),
            "implementation_effort": self.implementation_effort,
            "priority": self.priority,
        }


class CostAnalyzer:
    """Analyzes costs and provides optimization recommendations."""

    def __init__(self, cost_tracker: CostTracker):
        self.cost_tracker = cost_tracker
        logger.info("Cost analyzer initialized")

    def analyze_costs(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> dict:
        """Perform comprehensive cost analysis."""

        # Get cost summary
        summary = self.cost_tracker.get_summary(start_time, end_time)

        # Calculate metrics
        analysis = {
            "period": {
                "start": summary.period_start.isoformat(),
                "end": summary.period_end.isoformat(),
            },
            "total_cost": round(summary.total_cost, 2),
            "total_requests": summary.total_requests,
            "average_cost_per_request": round(
                summary.total_cost / max(summary.total_requests, 1), 4
            ),
            "cache_effectiveness": {
                "hit_rate": round(
                    summary.cached_requests / max(summary.total_requests, 1) * 100, 2
                ),
                "savings": round(summary.cache_savings, 2),
                "savings_percentage": round(
                    summary.cache_savings
                    / max(summary.total_cost + summary.cache_savings, 1)
                    * 100,
                    2,
                ),
            },
            "cost_breakdown": {
                "by_provider": summary.cost_by_provider,
                "by_model": summary.cost_by_model,
                "by_type": {
                    "prompt": round(summary.prompt_cost, 2),
                    "completion": round(summary.completion_cost, 2),
                },
            },
            "token_usage": {
                "total": summary.total_tokens,
                "prompt": summary.prompt_tokens,
                "completion": summary.completion_tokens,
                "average_per_request": summary.total_tokens // max(summary.total_requests, 1),
            },
        }

        # Add trends
        analysis["trends"] = self._analyze_trends()

        # Add optimizations
        analysis["optimizations"] = self._generate_optimizations(summary)

        return analysis

    def _analyze_trends(self) -> dict:
        """Analyze cost trends."""

        # Compare last 7 days to previous 7 days
        now = datetime.now()

        current_week = self.cost_tracker.get_summary(now - timedelta(days=7), now)

        previous_week = self.cost_tracker.get_summary(
            now - timedelta(days=14), now - timedelta(days=7)
        )

        # Calculate changes
        cost_change = current_week.total_cost - previous_week.total_cost
        cost_change_pct = (cost_change / max(previous_week.total_cost, 1)) * 100

        request_change = current_week.total_requests - previous_week.total_requests
        request_change_pct = (request_change / max(previous_week.total_requests, 1)) * 100

        return {
            "weekly_cost_change": round(cost_change, 2),
            "weekly_cost_change_percentage": round(cost_change_pct, 2),
            "weekly_request_change": request_change,
            "weekly_request_change_percentage": round(request_change_pct, 2),
            "cost_trend": "increasing" if cost_change > 0 else "decreasing",
            "daily_costs_last_7_days": self._get_daily_costs(7),
        }

    def _get_daily_costs(self, days: int) -> list[dict]:
        """Get daily costs for the last N days."""
        daily_costs = []

        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")

            cost = self.cost_tracker.daily_costs.get(date_str, 0)

            daily_costs.append({"date": date_str, "cost": round(cost, 2)})

        return list(reversed(daily_costs))

    def _generate_optimizations(self, summary) -> list[dict]:
        """Generate optimization recommendations."""
        optimizations = []

        # Check cache hit rate
        cache_hit_rate = summary.cached_requests / max(summary.total_requests, 1)
        if cache_hit_rate < 0.3:
            optimizations.append(
                CostOptimization(
                    title="Improve Cache Hit Rate",
                    description=f"Current cache hit rate is {cache_hit_rate*100:.1f}%. "
                    "Consider adjusting similarity threshold or warming cache with common queries.",
                    potential_savings=summary.total_cost * 0.2,
                    implementation_effort="low",
                    priority=1,
                )
            )

        # Check model usage
        if "model-4" in summary.cost_by_model:
            model4_cost = summary.cost_by_model["model-4"]
            if model4_cost > summary.total_cost * 0.5:
                optimizations.append(
                    CostOptimization(
                        title="Optimize Model Selection",
                        description="Over 50% of costs from expensive models. "
                        "Consider using model-3.5-turbo for simpler queries.",
                        potential_savings=model4_cost * 0.3,
                        implementation_effort="medium",
                        priority=2,
                    )
                )

        # Check token usage
        avg_tokens = summary.total_tokens / max(summary.total_requests, 1)
        if avg_tokens > 2000:
            optimizations.append(
                CostOptimization(
                    title="Reduce Token Usage",
                    description=f"Average token usage is {avg_tokens:.0f}. "
                    "Consider summarizing context or using shorter prompts.",
                    potential_savings=summary.total_cost * 0.15,
                    implementation_effort="medium",
                    priority=3,
                )
            )

        # Check completion vs prompt ratio
        if summary.completion_tokens > summary.prompt_tokens * 2:
            optimizations.append(
                CostOptimization(
                    title="Optimize Response Length",
                    description="Completion tokens are more than 2x prompt tokens. "
                    "Consider setting max_tokens limit or requesting concise responses.",
                    potential_savings=summary.completion_cost * 0.25,
                    implementation_effort="low",
                    priority=2,
                )
            )

        # Sort by priority
        optimizations.sort(key=lambda x: x.priority)

        return [opt.to_dict() for opt in optimizations]

    def get_tenant_analysis(self, tenant_id: str) -> dict:
        """Analyze costs for a specific tenant."""

        # Get tenant usage
        usage = self.cost_tracker.get_tenant_usage(tenant_id)

        # Add recommendations
        if usage["usage"]["cost"] > 100:
            usage["recommendations"] = [
                "Consider upgrading to enterprise plan for volume discounts",
                "Enable aggressive caching to reduce costs",
            ]
        elif usage["usage"]["cached_requests"] < usage["usage"]["requests"] * 0.3:
            usage["recommendations"] = [
                "Increase cache usage to reduce costs",
                "Use common query patterns for better cache hits",
            ]
        else:
            usage["recommendations"] = []

        return usage

    def generate_cost_report(self, format: str = "summary") -> str:
        """Generate cost report."""

        analysis = self.analyze_costs()

        if format == "summary":
            report = f"""
Cost Analysis Report
====================
Period: {analysis['period']['start']} to {analysis['period']['end']}

Total Cost: ${analysis['total_cost']}
Total Requests: {analysis['total_requests']}
Average Cost per Request: ${analysis['average_cost_per_request']}

Cache Performance:
- Hit Rate: {analysis['cache_effectiveness']['hit_rate']}%
- Savings: ${analysis['cache_effectiveness']['savings']}
- Savings Percentage: {analysis['cache_effectiveness']['savings_percentage']}%

Top Cost Drivers:
"""
            for model, cost in analysis["cost_breakdown"]["by_model"].items():
                report += f"- {model}: ${cost:.2f}\n"

            report += "\nOptimization Opportunities:\n"
            for opt in analysis["optimizations"]:
                report += f"- {opt['title']}: Potential savings ${opt['potential_savings']}\n"

            return report

        elif format == "json":
            import json

            return json.dumps(analysis, indent=2)

        else:
            raise ValueError(f"Unsupported format: {format}")

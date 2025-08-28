
from api.models.chat import ChatSession


class CostCalculator:
    def __init__(self):
        self.pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06, "name": "GPT-4"},
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002, "name": "GPT-3.5 Turbo"},
            "claude-3-opus": {"input": 0.015, "output": 0.075, "name": "Claude 3 Opus"},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015, "name": "Claude 3 Sonnet"},
        }

    def calculate_session_cost(self, session: ChatSession) -> dict:
        """Calculate total cost for a session"""
        return {
            "total_cost": session.metrics.get("total_cost", 0.0),
            "total_tokens": session.metrics.get("total_tokens", 0),
            "message_count": session.metrics.get("total_messages", 0),
            "average_cost_per_message": (
                session.metrics.get("total_cost", 0.0)
                / max(session.metrics.get("total_messages", 1), 1)
            ),
        }

    def calculate_cost_by_model(self, sessions: list[ChatSession]) -> dict[str, dict]:
        """Calculate cost breakdown by model across sessions"""
        model_costs = {}

        for session in sessions:
            model = session.config.get("model", "unknown")
            if model not in model_costs:
                model_costs[model] = {
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "session_count": 0,
                    "message_count": 0,
                }

            model_costs[model]["total_cost"] += session.metrics.get("total_cost", 0.0)
            model_costs[model]["total_tokens"] += session.metrics.get("total_tokens", 0)
            model_costs[model]["session_count"] += 1
            model_costs[model]["message_count"] += session.metrics.get("total_messages", 0)

        return model_costs

    def project_monthly_cost(
        self,
        daily_sessions: int,
        avg_messages_per_session: int,
        avg_tokens_per_message: int,
        model: str = "gpt-4",
    ) -> dict:
        """Project monthly costs based on usage patterns"""
        if model not in self.pricing:
            return {"error": "Unknown model"}

        # Estimate token distribution (60% input, 40% output)
        input_tokens_per_message = int(avg_tokens_per_message * 0.6)
        output_tokens_per_message = int(avg_tokens_per_message * 0.4)

        # Daily calculations
        daily_messages = daily_sessions * avg_messages_per_session
        daily_input_tokens = daily_messages * input_tokens_per_message
        daily_output_tokens = daily_messages * output_tokens_per_message

        # Cost calculations
        daily_input_cost = (daily_input_tokens / 1000) * self.pricing[model]["input"]
        daily_output_cost = (daily_output_tokens / 1000) * self.pricing[model]["output"]
        daily_total_cost = daily_input_cost + daily_output_cost

        # Monthly projections (30 days)
        monthly_cost = daily_total_cost * 30

        return {
            "model": self.pricing[model]["name"],
            "daily_cost": round(daily_total_cost, 2),
            "weekly_cost": round(daily_total_cost * 7, 2),
            "monthly_cost": round(monthly_cost, 2),
            "yearly_cost": round(monthly_cost * 12, 2),
            "daily_tokens": daily_input_tokens + daily_output_tokens,
            "monthly_tokens": (daily_input_tokens + daily_output_tokens) * 30,
            "cost_per_session": round(daily_total_cost / daily_sessions, 4),
        }

    def get_cost_optimization_suggestions(self, session_metrics: dict) -> list[str]:
        """Provide cost optimization suggestions based on usage"""
        suggestions = []

        avg_tokens_per_message = session_metrics.get("avg_tokens_per_message", 0)
        model = session_metrics.get("primary_model", "gpt-4")
        cache_hit_rate = session_metrics.get("cache_hit_rate", 0)

        # Token optimization
        if avg_tokens_per_message > 500:
            suggestions.append(
                "Consider implementing message summarization to reduce token usage. "
                "Average message length is high."
            )

        # Model selection
        if model == "gpt-4" and avg_tokens_per_message < 200:
            suggestions.append(
                "For simple queries, consider using GPT-3.5 Turbo which is 30x cheaper "
                "than GPT-4 for similar quality on basic tasks."
            )

        # Caching
        if cache_hit_rate < 0.2:
            suggestions.append(
                f"Cache hit rate is {cache_hit_rate:.1%}. Consider tuning semantic "
                "cache similarity threshold to improve cache utilization."
            )

        # Context management
        if session_metrics.get("avg_context_tokens", 0) > 2000:
            suggestions.append(
                "Large context sizes detected. Implement context compression or "
                "summarization to reduce costs."
            )

        return suggestions

"""Usage tracking and billing for multi-tenant system."""

import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class UsageTracker:
    """Track and manage tenant usage for billing."""

    def __init__(self, redis_client, db_session=None):
        self.redis = redis_client
        self.db = db_session

    async def track_api_call(
        self,
        tenant_id: str,
        endpoint: str,
        method: str,
        response_time_ms: float,
        status_code: int,
        metadata: dict | None = None,
    ):
        """Track API call for billing and analytics.

        Args:
            tenant_id: Tenant identifier
            endpoint: API endpoint
            method: HTTP method
            response_time_ms: Response time in milliseconds
            status_code: HTTP status code
            metadata: Additional metadata
        """
        timestamp = datetime.utcnow()

        # Create usage record
        usage_data = {
            "tenant_id": tenant_id,
            "endpoint": endpoint,
            "method": method,
            "response_time_ms": response_time_ms,
            "status_code": status_code,
            "timestamp": timestamp.isoformat(),
            "metadata": metadata or {},
        }

        # Track in Redis for real-time analytics
        await self._track_redis_metrics(tenant_id, "api_calls", timestamp)

        # Store detailed record
        if self.db:
            await self._store_api_usage(usage_data)

        # Update response time metrics
        await self._update_latency_metrics(tenant_id, endpoint, response_time_ms)

    async def track_token_usage(
        self,
        tenant_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost: float,
        metadata: dict | None = None,
    ):
        """Track token usage for LLM calls.

        Args:
            tenant_id: Tenant identifier
            model: Model used
            input_tokens: Input token count
            output_tokens: Output token count
            total_tokens: Total tokens
            cost: Calculated cost
            metadata: Additional metadata
        """
        timestamp = datetime.utcnow()

        # Create token usage record
        usage_data = {
            "tenant_id": tenant_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
            "timestamp": timestamp.isoformat(),
            "metadata": metadata or {},
        }

        # Track in Redis
        await self._track_redis_metrics(tenant_id, "tokens", timestamp, total_tokens)
        await self._track_redis_metrics(tenant_id, "cost", timestamp, cost)

        # Store in database
        if self.db:
            await self._store_token_usage(usage_data)

        # Update model-specific metrics
        await self._update_model_metrics(tenant_id, model, total_tokens, cost)

    async def track_websocket_usage(
        self,
        tenant_id: str,
        connection_id: str,
        messages_sent: int,
        messages_received: int,
        duration_seconds: float,
        metadata: dict | None = None,
    ):
        """Track WebSocket connection usage.

        Args:
            tenant_id: Tenant identifier
            connection_id: Connection identifier
            messages_sent: Number of messages sent
            messages_received: Number of messages received
            duration_seconds: Connection duration
            metadata: Additional metadata
        """
        timestamp = datetime.utcnow()

        # Create WebSocket usage record
        usage_data = {
            "tenant_id": tenant_id,
            "connection_id": connection_id,
            "messages_sent": messages_sent,
            "messages_received": messages_received,
            "duration_seconds": duration_seconds,
            "timestamp": timestamp.isoformat(),
            "metadata": metadata or {},
        }

        # Track in Redis
        total_messages = messages_sent + messages_received
        await self._track_redis_metrics(tenant_id, "websocket_messages", timestamp, total_messages)
        await self._track_redis_metrics(
            tenant_id, "websocket_duration", timestamp, duration_seconds
        )

        # Store in database
        if self.db:
            await self._store_websocket_usage(usage_data)

    async def track_storage_usage(
        self,
        tenant_id: str,
        storage_type: str,
        size_bytes: int,
        operation: str,
        metadata: dict | None = None,
    ):
        """Track storage usage.

        Args:
            tenant_id: Tenant identifier
            storage_type: Type of storage (file, cache, etc.)
            size_bytes: Size in bytes
            operation: Operation type (upload, delete, etc.)
            metadata: Additional metadata
        """
        timestamp = datetime.utcnow()

        # Convert to MB for tracking
        size_mb = size_bytes / (1024 * 1024)

        # Track in Redis
        if operation == "upload":
            await self._track_redis_metrics(tenant_id, "storage_mb", timestamp, size_mb)
        elif operation == "delete":
            await self._track_redis_metrics(tenant_id, "storage_mb", timestamp, -size_mb)

        # Store event
        if self.db:
            await self._store_storage_event(
                tenant_id, storage_type, size_bytes, operation, timestamp, metadata
            )

    async def get_usage_summary(
        self, tenant_id: str, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Get comprehensive usage summary for billing period.

        Args:
            tenant_id: Tenant identifier
            start_date: Period start
            end_date: Period end

        Returns:
            Usage summary with costs
        """
        summary = {
            "tenant_id": tenant_id,
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "usage": {},
            "costs": {},
            "total_cost": 0.0,
        }

        # Get usage metrics from Redis
        metrics = ["api_calls", "tokens", "websocket_messages", "storage_mb"]

        for metric in metrics:
            total = await self._get_period_total(tenant_id, metric, start_date, end_date)
            summary["usage"][metric] = total

            # Calculate cost
            unit_cost = self._get_unit_cost(metric)
            metric_cost = total * unit_cost
            summary["costs"][metric] = metric_cost
            summary["total_cost"] += metric_cost

        # Add tier discounts
        discount = await self._calculate_discount(tenant_id, summary["total_cost"])
        summary["discount"] = discount
        summary["final_cost"] = summary["total_cost"] - discount

        return summary

    async def get_real_time_usage(self, tenant_id: str) -> dict[str, Any]:
        """Get real-time usage metrics.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Current usage metrics
        """
        today = datetime.utcnow().date()

        metrics = {}
        metric_types = ["api_calls", "tokens", "websocket_messages", "storage_mb", "cost"]

        for metric_type in metric_types:
            # Get today's usage
            day_key = f"usage:{tenant_id}:{today}:{metric_type}"
            day_value = await self.redis.get(day_key)

            # Get this hour's usage
            hour = datetime.utcnow().hour
            hour_key = f"usage:{tenant_id}:{today}:{hour}:{metric_type}"
            hour_value = await self.redis.get(hour_key)

            metrics[metric_type] = {
                "today": float(day_value) if day_value else 0,
                "this_hour": float(hour_value) if hour_value else 0,
            }

        return {
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": metrics,
        }

    async def get_usage_trends(self, tenant_id: str, days: int = 7) -> dict[str, Any]:
        """Get usage trends over time.

        Args:
            tenant_id: Tenant identifier
            days: Number of days to analyze

        Returns:
            Usage trends
        """
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days - 1)

        trends = {"tenant_id": tenant_id, "period_days": days, "daily_usage": []}

        current_date = start_date
        while current_date <= end_date:
            day_metrics = {}

            for metric in ["api_calls", "tokens", "cost"]:
                key = f"usage:{tenant_id}:{current_date}:{metric}"
                value = await self.redis.get(key)
                day_metrics[metric] = float(value) if value else 0

            trends["daily_usage"].append({"date": current_date.isoformat(), "metrics": day_metrics})

            current_date += timedelta(days=1)

        # Calculate averages and trends
        if trends["daily_usage"]:
            total_api_calls = sum(d["metrics"]["api_calls"] for d in trends["daily_usage"])
            total_tokens = sum(d["metrics"]["tokens"] for d in trends["daily_usage"])
            total_cost = sum(d["metrics"]["cost"] for d in trends["daily_usage"])

            trends["averages"] = {
                "api_calls_per_day": total_api_calls / days,
                "tokens_per_day": total_tokens / days,
                "cost_per_day": total_cost / days,
            }

            # Calculate growth rate (last 3 days vs previous 3 days)
            if days >= 6:
                recent = trends["daily_usage"][-3:]
                previous = trends["daily_usage"][-6:-3]

                recent_cost = sum(d["metrics"]["cost"] for d in recent)
                previous_cost = sum(d["metrics"]["cost"] for d in previous)

                if previous_cost > 0:
                    growth_rate = ((recent_cost - previous_cost) / previous_cost) * 100
                else:
                    growth_rate = 0

                trends["growth_rate"] = growth_rate

        return trends

    async def generate_invoice(self, tenant_id: str, billing_period: str) -> dict[str, Any]:
        """Generate invoice for billing period.

        Args:
            tenant_id: Tenant identifier
            billing_period: Billing period (YYYY-MM)

        Returns:
            Invoice data
        """
        # Parse billing period
        year, month = map(int, billing_period.split("-"))
        start_date = datetime(year, month, 1)

        # Calculate end date (last day of month)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)

        # Get usage summary
        usage = await self.get_usage_summary(tenant_id, start_date, end_date)

        # Generate invoice
        invoice = {
            "invoice_id": f"INV-{tenant_id}-{billing_period}",
            "tenant_id": tenant_id,
            "billing_period": billing_period,
            "generated_at": datetime.utcnow().isoformat(),
            "due_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "line_items": [],
            "subtotal": usage["total_cost"],
            "discount": usage.get("discount", 0),
            "tax": 0,  # Could be calculated based on location
            "total": usage["final_cost"],
        }

        # Add line items
        for metric, amount in usage["usage"].items():
            if amount > 0:
                unit_cost = self._get_unit_cost(metric)
                invoice["line_items"].append(
                    {
                        "description": self._get_metric_description(metric),
                        "quantity": amount,
                        "unit_price": unit_cost,
                        "total": amount * unit_cost,
                    }
                )

        return invoice

    async def _track_redis_metrics(
        self, tenant_id: str, metric_type: str, timestamp: datetime, amount: float = 1
    ):
        """Track metrics in Redis.

        Args:
            tenant_id: Tenant identifier
            metric_type: Type of metric
            timestamp: Timestamp
            amount: Amount to track
        """
        # Daily tracking
        day_key = f"usage:{tenant_id}:{timestamp.date()}:{metric_type}"
        await self.redis.incrbyfloat(day_key, amount)
        await self.redis.expire(day_key, 86400 * 35)  # 35 days

        # Hourly tracking
        hour_key = f"usage:{tenant_id}:{timestamp.date()}:{timestamp.hour}:{metric_type}"
        await self.redis.incrbyfloat(hour_key, amount)
        await self.redis.expire(hour_key, 86400 * 2)  # 2 days

        # Monthly tracking
        month_key = f"usage:{tenant_id}:{timestamp.strftime('%Y-%m')}:{metric_type}"
        await self.redis.incrbyfloat(month_key, amount)
        await self.redis.expire(month_key, 86400 * 400)  # ~13 months

    async def _update_latency_metrics(self, tenant_id: str, endpoint: str, response_time_ms: float):
        """Update latency metrics.

        Args:
            tenant_id: Tenant identifier
            endpoint: API endpoint
            response_time_ms: Response time
        """
        # Store in sorted set for percentile calculations
        key = f"latency:{tenant_id}:{datetime.utcnow().date()}:{endpoint}"
        await self.redis.zadd(key, {str(datetime.utcnow().timestamp()): response_time_ms})
        await self.redis.expire(key, 86400)  # 1 day

    async def _update_model_metrics(self, tenant_id: str, model: str, tokens: int, cost: float):
        """Update model-specific metrics.

        Args:
            tenant_id: Tenant identifier
            model: Model name
            tokens: Token count
            cost: Cost
        """
        date = datetime.utcnow().date()

        # Track tokens per model
        model_tokens_key = f"model_usage:{tenant_id}:{date}:{model}:tokens"
        await self.redis.incrbyfloat(model_tokens_key, tokens)
        await self.redis.expire(model_tokens_key, 86400 * 35)

        # Track cost per model
        model_cost_key = f"model_usage:{tenant_id}:{date}:{model}:cost"
        await self.redis.incrbyfloat(model_cost_key, cost)
        await self.redis.expire(model_cost_key, 86400 * 35)

    async def _get_period_total(
        self, tenant_id: str, metric: str, start_date: datetime, end_date: datetime
    ) -> float:
        """Get total usage for period.

        Args:
            tenant_id: Tenant identifier
            metric: Metric type
            start_date: Start date
            end_date: End date

        Returns:
            Total usage
        """
        total = 0.0
        current_date = start_date.date()

        while current_date <= end_date.date():
            key = f"usage:{tenant_id}:{current_date}:{metric}"
            value = await self.redis.get(key)
            if value:
                total += float(value)
            current_date += timedelta(days=1)

        return total

    def _get_unit_cost(self, metric: str) -> float:
        """Get unit cost for metric.

        Args:
            metric: Metric type

        Returns:
            Cost per unit
        """
        costs = {
            "api_calls": 0.001,  # $0.001 per API call
            "tokens": 0.00002,  # $0.00002 per token
            "websocket_messages": 0.0001,  # $0.0001 per message
            "storage_mb": 0.10,  # $0.10 per MB per month
        }

        return costs.get(metric, 0.0)

    def _get_metric_description(self, metric: str) -> str:
        """Get human-readable metric description.

        Args:
            metric: Metric type

        Returns:
            Description
        """
        descriptions = {
            "api_calls": "API Calls",
            "tokens": "LLM Tokens",
            "websocket_messages": "WebSocket Messages",
            "storage_mb": "Storage (MB)",
        }

        return descriptions.get(metric, metric)

    async def _calculate_discount(self, tenant_id: str, total_cost: float) -> float:
        """Calculate tenant discount.

        Args:
            tenant_id: Tenant identifier
            total_cost: Total cost before discount

        Returns:
            Discount amount
        """
        # Could be based on tier, volume, contract, etc.
        # For now, simple volume discount
        if total_cost > 1000:
            return total_cost * 0.10  # 10% discount
        elif total_cost > 500:
            return total_cost * 0.05  # 5% discount

        return 0.0

    async def _store_api_usage(self, usage_data: dict):
        """Store API usage in database."""
        if not self.db:
            return

        try:
            from api.models import ApiUsage

            usage = ApiUsage(**usage_data)
            self.db.add(usage)
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to store API usage: {e}")

    async def _store_token_usage(self, usage_data: dict):
        """Store token usage in database."""
        if not self.db:
            return

        try:
            from api.models import TokenUsage

            usage = TokenUsage(**usage_data)
            self.db.add(usage)
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to store token usage: {e}")

    async def _store_websocket_usage(self, usage_data: dict):
        """Store WebSocket usage in database."""
        if not self.db:
            return

        try:
            from api.models import WebSocketUsage

            usage = WebSocketUsage(**usage_data)
            self.db.add(usage)
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to store WebSocket usage: {e}")

    async def _store_storage_event(
        self,
        tenant_id: str,
        storage_type: str,
        size_bytes: int,
        operation: str,
        timestamp: datetime,
        metadata: dict | None,
    ):
        """Store storage event in database."""
        if not self.db:
            return

        try:
            from api.models import StorageEvent

            event = StorageEvent(
                tenant_id=tenant_id,
                storage_type=storage_type,
                size_bytes=size_bytes,
                operation=operation,
                timestamp=timestamp,
                metadata=metadata or {},
            )

            self.db.add(event)
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to store storage event: {e}")

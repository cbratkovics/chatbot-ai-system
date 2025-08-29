"""Tenant configuration models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TenantLimits(BaseModel):
    """Tenant rate limits and quotas."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    tokens_per_day: int = 100000
    max_concurrent_requests: int = 10


class TenantUsage(BaseModel):
    """Tenant usage tracking."""

    requests_today: int = 0
    tokens_used_today: int = 0
    last_request_at: datetime | None = None
    monthly_cost: float = 0.0


class TenantConfig(BaseModel):
    """Tenant configuration."""

    tenant_id: str
    name: str
    tier: str = "standard"
    status: str = "active"
    limits: TenantLimits = TenantLimits()
    usage: TenantUsage = TenantUsage()
    features: list[str] = []
    metadata: dict[str, Any] = {}

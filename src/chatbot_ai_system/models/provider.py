"""Provider configuration models."""

from typing import Any, Dict, List, Tuple, Optional
from enum import Enum

from pydantic import BaseModel


class ProviderStatus(str, Enum):
    """Provider status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class ProviderMetrics(BaseModel):
    """Provider metrics model."""

    requests_total: int = 0
    requests_failed: int = 0
    average_latency_ms: float = 0.0
    tokens_used: int = 0
    error_rate: float = 0.0


class ProviderConfig(BaseModel):
    """Provider configuration model."""

    name: str
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: int = 30
    max_retries: int = 3
    models: list[str] = []
    status: ProviderStatus = ProviderStatus.ACTIVE

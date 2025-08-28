"""Provider configuration models."""
from pydantic import BaseModel
from typing import Dict, Optional, List
from enum import Enum

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
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout_seconds: int = 30
    max_retries: int = 3
    models: List[str] = []
    status: ProviderStatus = ProviderStatus.ACTIVE

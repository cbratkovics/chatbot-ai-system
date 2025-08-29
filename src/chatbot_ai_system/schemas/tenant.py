"""Tenant-related schemas."""

from datetime import datetime
from typing import Dict, Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TenantQuota(BaseModel):
    """Tenant quota configuration."""
    monthly_requests: int = Field(100000, description="Monthly request limit")
    monthly_tokens: int = Field(10000000, description="Monthly token limit")
    max_conversation_length: int = Field(100, description="Maximum conversation length")
    max_message_length: int = Field(4000, description="Maximum message length")
    max_concurrent_requests: int = Field(10, description="Maximum concurrent requests")
    
    # Rate limits
    requests_per_minute: int = Field(100, description="Requests per minute")
    requests_per_hour: int = Field(5000, description="Requests per hour")
    tokens_per_minute: int = Field(10000, description="Tokens per minute")
    tokens_per_hour: int = Field(500000, description="Tokens per hour")
    
    # Feature access
    allowed_models: Optional[list[str]] = Field(None, description="Allowed models")
    allowed_providers: Optional[list[str]] = Field(None, description="Allowed providers")
    enable_streaming: bool = Field(True, description="Enable streaming responses")
    enable_function_calling: bool = Field(False, description="Enable function calling")
    enable_vision: bool = Field(False, description="Enable vision capabilities")
    enable_voice: bool = Field(False, description="Enable voice capabilities")


class TenantUsage(BaseModel):
    """Tenant usage tracking."""
    tenant_id: str = Field(..., description="Tenant identifier")
    period: str = Field(..., description="Usage period (e.g., '2024-01')")
    
    # Request metrics
    total_requests: int = Field(0, description="Total requests made")
    successful_requests: int = Field(0, description="Successful requests")
    failed_requests: int = Field(0, description="Failed requests")
    
    # Token metrics
    total_tokens: int = Field(0, description="Total tokens used")
    prompt_tokens: int = Field(0, description="Prompt tokens used")
    completion_tokens: int = Field(0, description="Completion tokens used")
    
    # Cost metrics
    total_cost: float = Field(0.0, description="Total cost in USD")
    provider_costs: Dict[str, float] = Field(default_factory=dict, description="Cost per provider")
    
    # Performance metrics
    average_latency_ms: float = Field(0.0, description="Average response latency")
    p95_latency_ms: float = Field(0.0, description="95th percentile latency")
    p99_latency_ms: float = Field(0.0, description="99th percentile latency")
    
    # Cache metrics
    cache_hits: int = Field(0, description="Number of cache hits")
    cache_misses: int = Field(0, description="Number of cache misses")
    cache_hit_rate: float = Field(0.0, description="Cache hit rate percentage")
    
    # Timestamps
    first_request_at: Optional[datetime] = Field(None, description="First request timestamp")
    last_request_at: Optional[datetime] = Field(None, description="Last request timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")


class Tenant(BaseModel):
    """Tenant model."""
    id: str = Field(default_factory=lambda: str(uuid4()), description="Tenant ID")
    name: str = Field(..., description="Tenant name")
    description: Optional[str] = Field(None, description="Tenant description")
    
    # Status
    active: bool = Field(True, description="Whether tenant is active")
    tier: str = Field("free", description="Subscription tier")
    
    # Configuration
    quota: TenantQuota = Field(default_factory=TenantQuota, description="Tenant quota")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Tenant settings")
    
    # API keys
    api_keys: list[str] = Field(default_factory=list, description="API keys")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    tags: list[str] = Field(default_factory=list, description="Tenant tags")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    
    # Contact information
    email: Optional[str] = Field(None, description="Contact email")
    contact_name: Optional[str] = Field(None, description="Contact person name")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
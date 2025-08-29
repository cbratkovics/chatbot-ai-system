"""Database models for chatbot system."""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Column, String, Text, DateTime, JSON, Float, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID

from chatbot_ai_system.database import Base


class ChatHistory(Base):
    """Chat history model."""
    
    __tablename__ = "chat_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)
    tenant_id = Column(String, nullable=True, index=True)
    
    # Request data
    messages = Column(JSON, nullable=False)
    model = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, nullable=True)
    
    # Response data
    response = Column(Text, nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # Metadata
    latency_ms = Column(Float, nullable=True)
    cached = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "messages": self.messages,
            "model": self.model,
            "provider": self.provider,
            "response": self.response,
            "tokens": {
                "prompt": self.prompt_tokens,
                "completion": self.completion_tokens,
                "total": self.total_tokens,
            },
            "latency_ms": self.latency_ms,
            "cached": self.cached,
            "created_at": self.created_at.isoformat(),
        }


class ApiKey(Base):
    """API key model for authentication."""
    
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    tenant_id = Column(String, nullable=True, index=True)
    
    # Permissions
    rate_limit = Column(Integer, default=100)  # Requests per minute
    allowed_models = Column(JSON, default=list)  # Empty list means all models
    allowed_providers = Column(JSON, default=list)  # Empty list means all providers
    
    # Status
    active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    
    def is_valid(self) -> bool:
        """Check if API key is valid."""
        if not self.active:
            return False
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        return True


class ProviderMetric(Base):
    """Provider metrics for monitoring."""
    
    __tablename__ = "provider_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String, nullable=False, index=True)
    
    # Metrics
    requests_total = Column(Integer, default=0)
    requests_successful = Column(Integer, default=0)
    requests_failed = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    average_latency_ms = Column(Float, default=0.0)
    
    # Status
    status = Column(String, default="healthy")
    last_error = Column(Text, nullable=True)
    
    # Timestamps
    last_request_at = Column(DateTime, nullable=True)
    last_error_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
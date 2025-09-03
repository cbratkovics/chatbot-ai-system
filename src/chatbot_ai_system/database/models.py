"""Database models for multi-tenant chatbot system."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Tenant(Base):
    """Tenant model for multi-tenancy."""

    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)

    # Configuration
    max_users = Column(Integer, default=10)
    max_conversations = Column(Integer, default=1000)
    max_messages_per_day = Column(Integer, default=10000)
    allowed_models = Column(JSON, default=["model-3.5-turbo"])

    # Features
    features = Column(JSON, default={})
    settings = Column(JSON, default={})

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    conversations = relationship(
        "Conversation", back_populates="tenant", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_tenant_slug", "slug"),
        Index("idx_tenant_active", "is_active"),
    )


class User(Base):
    """User model with tenant association."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    # Authentication
    email = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)

    # Profile
    full_name = Column(String(255))
    avatar_url = Column(String(500))

    # Roles and permissions
    roles = Column(JSON, default=["user"])
    permissions = Column(JSON, default=[])

    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    conversations = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_tenant_email"),
        UniqueConstraint("tenant_id", "username", name="uq_tenant_username"),
        Index("idx_user_tenant", "tenant_id"),
        Index("idx_user_email", "email"),
        Index("idx_user_active", "is_active"),
    )


class Conversation(Base):
    """Conversation model for chat sessions."""

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Conversation metadata
    title = Column(String(500))
    model = Column(String(100), default="model-3.5-turbo")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=1000)

    # Statistics
    message_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="conversations")
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_conversation_tenant", "tenant_id"),
        Index("idx_conversation_user", "user_id"),
        Index("idx_conversation_created", "created_at"),
    )


class Message(Base):
    """Message model for conversation history."""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Message content
    role = Column(String(50), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)

    # Metadata
    model = Column(String(100))
    provider = Column(String(100))

    # Tokens and cost
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)

    # Performance
    latency_ms = Column(Float)
    cached = Column(Boolean, default=False)

    # Additional data
    metadata = Column(JSON, default={})

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    user = relationship("User", back_populates="messages")

    __table_args__ = (
        Index("idx_message_conversation", "conversation_id"),
        Index("idx_message_user", "user_id"),
        Index("idx_message_created", "created_at"),
        Index("idx_message_role", "role"),
    )

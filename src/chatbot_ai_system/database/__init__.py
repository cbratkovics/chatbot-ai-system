"""Database module for persistence layer."""

from typing import Optional

from .models import Base, Chat, Conversation, Message, Tenant, User
from .session import SessionLocal, engine, get_db

# Global variables for async support
_async_engine: Optional[object] = None
_async_session_factory: Optional[object] = None


async def init_db():
    """Initialize database connection."""
    global _async_engine, _async_session_factory
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    from chatbot_ai_system.config.settings import settings

    _async_engine = create_async_engine(
        settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
        echo=settings.is_development,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )

    _async_session_factory = sessionmaker(
        _async_engine, class_=AsyncSession, expire_on_commit=False
    )


async def close_db():
    """Close database connection."""
    global _async_engine
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None


async def get_async_session():
    """Get async database session."""
    if not _async_session_factory:
        await init_db()

    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Alias Chat to match expected import
Chat = Conversation


async def get_async_engine():
    """Get or create async engine."""
    global _async_engine
    if not _async_engine:
        await init_db()
    return _async_engine


async def create_database_connection():
    """Create database connection."""
    return await get_async_engine()


async def get_read_replica_session():
    """Get read replica session (or main session as fallback)."""
    return await get_async_session()


__all__ = [
    "Base",
    "Tenant",
    "User",
    "Conversation",
    "Chat",
    "Message",
    "get_db",
    "engine",
    "SessionLocal",
    "init_db",
    "close_db",
    "get_async_session",
    "get_async_engine",
    "create_database_connection",
    "get_read_replica_session",
]

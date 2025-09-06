"""Database session management."""

from typing import Generator, Optional
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config.settings import settings

# Don't create engine at import time
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Get or create database engine (lazy initialization)."""
    global _engine
    if _engine is None:
        if not settings.database_url:
            # For tests, use SQLite in-memory as fallback
            if settings.environment == "test":
                database_url = "sqlite:///:memory:"
            else:
                raise ValueError("DATABASE_URL is required but not set")
        else:
            database_url = settings.database_url
        
        _engine = create_engine(
            database_url,
            echo=settings.is_development,
            pool_size=20 if "postgresql" in database_url else 5,
            max_overflow=40 if "postgresql" in database_url else 10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    """Get or create session factory (lazy initialization)."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=get_engine()
        )
    return _SessionLocal


# Maintain backward compatibility with module-level variables
# These will be accessed as needed, triggering lazy initialization
class _LazyEngine:
    def __getattr__(self, name):
        return getattr(get_engine(), name)
    
    def __repr__(self):
        return repr(get_engine())


class _LazySessionLocal:
    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)
    
    def __getattr__(self, name):
        return getattr(get_session_factory(), name)


engine = _LazyEngine()
SessionLocal = _LazySessionLocal()


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()

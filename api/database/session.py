"""Database session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..app.config import settings

# Create engine
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

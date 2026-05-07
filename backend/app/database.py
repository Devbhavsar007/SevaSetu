"""
Database engine, session management, and initialization.
Uses SQLAlchemy 2.0 with SQLite (local dev) or PostgreSQL (production).
"""

import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from sqlalchemy.pool import QueuePool, StaticPool

from .config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# --- Engine ---
# Conditionally set connect_args: check_same_thread is SQLite-only
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

# Use appropriate pool for each DB
if "sqlite" in settings.DATABASE_URL:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        echo=settings.DEBUG,
        poolclass=StaticPool if ":memory:" in settings.DATABASE_URL else None,
        pool_pre_ping=True,
    )
else:
    # PostgreSQL — use QueuePool with sensible defaults
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=300,
    )


# Enable WAL mode and foreign keys for SQLite (better concurrency & integrity)
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()


# --- Session ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def get_db():
    """
    FastAPI dependency that provides a DB session per request.
    Ensures the session is closed after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_database_engine_name() -> str:
    """Return the database engine type: 'postgresql' or 'sqlite'."""
    if "postgresql" in settings.DATABASE_URL or "postgres" in settings.DATABASE_URL:
        return "postgresql"
    return "sqlite"


def init_db():
    """
    Create all tables defined by ORM models.
    Called once on application startup.
    """
    from . import models  # noqa: F401 — ensures models are registered
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database tables created/verified successfully. Engine: {get_database_engine_name()}")

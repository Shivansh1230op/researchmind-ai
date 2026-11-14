"""SQLAlchemy database engine and session management.

Provides a synchronous engine (SQLite for dev, swappable to PostgreSQL by
changing the ``DATABASE_URL`` in the environment) and a session factory.
The session is managed as a FastAPI dependency so each request gets its
own session and it is automatically closed when the request finishes.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Create the SQLAlchemy engine.
# For SQLite we need ``check_same_thread=False`` because FastAPI uses
# a thread pool for synchronous endpoints.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=settings.debug,
)

# Enable WAL mode for SQLite for better concurrent read performance
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base — all ORM models inherit from this
Base = declarative_base()


def init_db() -> None:
    """Create all database tables.

    Called once at application startup.  In production you would use
    Alembic migrations instead, but for development this is sufficient.
    """
    # Import models so they are registered on Base.metadata
    from app.database import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session.

    Usage in a route::

        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for using a session outside of FastAPI routes.

    Usage::

        with get_db_context() as db:
            db.query(Document).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

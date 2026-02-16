"""
Sessions synchrones pour les tâches Celery et les dépendances sync
"""

from typing import Generator
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings

_base_url = make_url(settings.DATABASE_URL)

if "+asyncpg" in _base_url.drivername:
    sync_driver = _base_url.drivername.replace("+asyncpg", "+psycopg2")
else:
    sync_driver = _base_url.drivername

# Build sync URL manually to avoid URL encoding issues with make_url().set()
# The issue: URL.set() can mangle special characters when converting back to string
sync_url_str = f"{_base_url.drivername.replace('+asyncpg', '+psycopg2')}://{_base_url.username}:{_base_url.password}@{_base_url.host}:{_base_url.port}/{_base_url.database}"

engine = create_engine(sync_url_str, pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_session() -> Session:
    """Retourne une session synchrone non gérée."""
    return SessionLocal()


def get_sync_db() -> Generator[Session, None, None]:
    """Dépendance FastAPI pour obtenir une session synchrone."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_sync_db_context() -> Generator[Session, None, None]:
    """Context manager pour utiliser une session sync dans les tâches Celery."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

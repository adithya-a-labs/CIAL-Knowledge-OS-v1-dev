"""Database engine and session factory."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings


def get_database_url() -> str | None:
    return settings.database_url or None


def create_database_engine(database_url: str | None = None) -> Engine | None:
    url = database_url or get_database_url()
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True, future=True)


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False) if engine else None


def get_db_session() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured.")
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


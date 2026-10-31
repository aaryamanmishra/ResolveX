"""Database engine, declarative base, and session factory for ResolveX AI.

PRD §8.2 & §12.1: Relational storage for canonical payments, cases, approvals,
audit events, and users. Supports PostgreSQL in production and SQLite in local/test.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.app.config import settings


class Base(DeclarativeBase):
    """Base declarative class for all ORM models."""

    pass


def get_async_database_url(url: str) -> str:
    """Normalize database URL for async SQLAlchemy driver."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


# Engine initialization
database_url = get_async_database_url(settings.DATABASE_URL)
# If in demo/test mode and default postgres url is unchanged, use in-memory sqlite
if settings.DEMO_MODE and "localhost:5432" in database_url:
    database_url = "sqlite+aiosqlite:///:memory:"

engine: AsyncEngine = create_async_engine(
    database_url,
    echo=False,
    future=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency providing an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

import asyncio
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("infrastructure.postgres")


def create_database_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create a production-configured SQLAlchemy AsyncEngine with connection pooling."""
    cfg = settings or get_settings()
    logger.info(
        "Creating PostgreSQL asynchronous engine",
        target=cfg.sanitized_database_url,
        pool_size=cfg.DATABASE_POOL_SIZE,
        max_overflow=cfg.DATABASE_MAX_OVERFLOW,
    )
    return create_async_engine(
        cfg.DATABASE_URL,
        pool_size=cfg.DATABASE_POOL_SIZE,
        max_overflow=cfg.DATABASE_MAX_OVERFLOW,
        pool_timeout=cfg.DATABASE_POOL_TIMEOUT,
        pool_recycle=cfg.DATABASE_POOL_RECYCLE,
        pool_pre_ping=True,
        echo=cfg.DEBUG,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory configured to produce non-expiring sessions."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def check_database_connectivity(engine: AsyncEngine | None, timeout: float = 3.0) -> bool:
    """Execute lightweight SELECT 1 probe to verify database reachability."""
    if engine is None:
        return False
    try:
        async with asyncio.timeout(timeout):
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                return result.scalar() == 1
    except Exception as exc:
        logger.warning("PostgreSQL connectivity check failed", error=str(exc))
        return False


async def dispose_database_engine(engine: AsyncEngine) -> None:
    """Dispose of the connection pool and all active database connections."""
    logger.info("Disposing PostgreSQL connection pool")
    await engine.dispose()


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an AsyncSession from the application state factory."""
    session_factory: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "db_session_factory", None
    )

    if session_factory is None:
        raise RuntimeError("Database session factory is not initialized on application state.")

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

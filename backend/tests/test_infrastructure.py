from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.postgres import (
    check_database_connectivity,
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
    get_db_session,
)
from app.db.qdrant import (
    check_qdrant_connectivity,
    close_qdrant_client,
    create_qdrant_client,
    get_qdrant,
)
from app.db.redis import (
    check_redis_connectivity,
    close_redis_client,
    create_redis_client,
    get_redis,
)


def test_create_database_engine() -> None:
    """Verify AsyncEngine creation with configured pool attributes."""
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/testdb",
        DATABASE_POOL_SIZE=5,
        DATABASE_MAX_OVERFLOW=10,
    )
    engine = create_database_engine(settings)
    assert isinstance(engine, AsyncEngine)
    assert engine.pool.size() == 5  # type: ignore[attr-defined]


def test_create_session_factory() -> None:
    """Verify async sessionmaker returns configured session factory."""
    settings = Settings(DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/testdb")
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    assert isinstance(factory, async_sessionmaker)


@pytest.mark.asyncio
async def test_dispose_database_engine() -> None:
    """Verify engine disposal cleans up pool without error."""
    settings = Settings(DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/testdb")
    engine = create_database_engine(settings)
    await dispose_database_engine(engine)


def test_create_redis_client() -> None:
    """Verify Redis asyncio client creation."""
    settings = Settings(REDIS_URL="redis://localhost:6379/1")
    client = create_redis_client(settings)
    assert isinstance(client, Redis)


@pytest.mark.asyncio
async def test_close_redis_client() -> None:
    """Verify Redis client close releases resources."""
    mock_redis = AsyncMock(spec=Redis)
    await close_redis_client(mock_redis)
    mock_redis.aclose.assert_awaited_once()


def test_create_qdrant_client() -> None:
    """Verify Qdrant client creation with custom URL and timeout."""
    settings = Settings(QDRANT_URL="http://qdrant.internal:6333", QDRANT_TIMEOUT=10)
    client = create_qdrant_client(settings)
    assert isinstance(client, AsyncQdrantClient)


@pytest.mark.asyncio
async def test_close_qdrant_client() -> None:
    """Verify Qdrant client close invokes client close."""
    mock_qdrant = AsyncMock(spec=AsyncQdrantClient)
    await close_qdrant_client(mock_qdrant)
    mock_qdrant.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_session_dependency() -> None:
    """Verify get_db_session yields session and handles commit/close."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_session

    mock_request = MagicMock(spec=Request)
    mock_request.app.state.db_session_factory = mock_factory

    sessions: list[AsyncSession] = []
    async for s in get_db_session(mock_request):
        sessions.append(s)

    assert len(sessions) == 1
    assert sessions[0] == mock_session
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_session_uninitialized_raises() -> None:
    """Verify get_db_session raises RuntimeError if session factory is not in state."""
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.db_session_factory = None

    with pytest.raises(RuntimeError, match="Database session factory is not initialized"):
        async for _ in get_db_session(mock_request):
            pass


def test_get_redis_dependency() -> None:
    """Verify get_redis retrieves client from application state."""
    mock_redis = MagicMock(spec=Redis)
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.redis_client = mock_redis

    retrieved = get_redis(mock_request)
    assert retrieved == mock_redis


def test_get_redis_uninitialized_raises() -> None:
    """Verify get_redis raises RuntimeError when redis_client is missing."""
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.redis_client = None

    with pytest.raises(RuntimeError, match="Redis client is not initialized"):
        get_redis(mock_request)


def test_get_qdrant_dependency() -> None:
    """Verify get_qdrant retrieves client from application state."""
    mock_qdrant = MagicMock(spec=AsyncQdrantClient)
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.qdrant_client = mock_qdrant

    retrieved = get_qdrant(mock_request)
    assert retrieved == mock_qdrant


def test_get_qdrant_uninitialized_raises() -> None:
    """Verify get_qdrant raises RuntimeError when qdrant_client is missing."""
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.qdrant_client = None

    with pytest.raises(RuntimeError, match="Qdrant client is not initialized"):
        get_qdrant(mock_request)


@pytest.mark.asyncio
async def test_check_database_connectivity_handles_error() -> None:
    """Verify check_database_connectivity returns False gracefully on error."""
    mock_engine = MagicMock(spec=AsyncEngine)
    mock_engine.connect.side_effect = Exception("Connection refused")
    is_ok = await check_database_connectivity(mock_engine, timeout=1.0)
    assert is_ok is False


@pytest.mark.asyncio
async def test_check_redis_connectivity_handles_error() -> None:
    """Verify check_redis_connectivity returns False gracefully on error."""
    mock_redis = AsyncMock(spec=Redis)
    mock_redis.ping.side_effect = Exception("Connection timed out")
    is_ok = await check_redis_connectivity(mock_redis, timeout=1.0)
    assert is_ok is False


@pytest.mark.asyncio
async def test_check_qdrant_connectivity_handles_error() -> None:
    """Verify check_qdrant_connectivity returns False gracefully on error."""
    mock_qdrant = AsyncMock(spec=AsyncQdrantClient)
    mock_qdrant.get_collections.side_effect = Exception("Service unavailable")
    is_ok = await check_qdrant_connectivity(mock_qdrant, timeout=1.0)
    assert is_ok is False

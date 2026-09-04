import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.db.postgres import (
    check_database_connectivity,
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from app.db.qdrant import (
    check_qdrant_connectivity,
    close_qdrant_client,
    create_qdrant_client,
)
from app.db.redis import (
    check_redis_connectivity,
    close_redis_client,
    create_redis_client,
)
from app.main import create_app

# Skip this entire module if RUN_INTEGRATION_TESTS is not truthy
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS", "false").lower() not in ("true", "1"),
    reason=(
        "Integration tests require running infrastructure services. "
        "Set RUN_INTEGRATION_TESTS=true to enable."
    ),
)


@pytest.mark.asyncio
async def test_postgres_live_connectivity() -> None:
    """Verify live PostgreSQL connection and session execution of SELECT 1."""
    settings = get_settings()
    engine = create_database_engine(settings)
    try:
        is_reachable = await check_database_connectivity(engine)
        assert is_reachable is True, "PostgreSQL failed connectivity check"

        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
    finally:
        await dispose_database_engine(engine)


@pytest.mark.asyncio
async def test_redis_live_operations() -> None:
    """Verify live Redis client ping, temporary key write, read, and cleanup."""
    settings = get_settings()
    client = create_redis_client(settings)
    try:
        is_reachable = await check_redis_connectivity(client)
        assert is_reachable is True, "Redis failed connectivity probe"

        test_key = f"test_probe_{uuid.uuid4().hex[:8]}"
        await client.set(test_key, "active", ex=10)
        value = await client.get(test_key)
        assert value == "active"
        await client.delete(test_key)
    finally:
        await close_redis_client(client)


@pytest.mark.asyncio
async def test_qdrant_live_connectivity() -> None:
    """Verify live Qdrant cluster connection without polluting collections."""
    settings = get_settings()
    client = create_qdrant_client(settings)
    try:
        is_reachable = await check_qdrant_connectivity(client)
        assert is_reachable is True, "Qdrant failed connectivity probe"
        collections = await client.get_collections()
        assert collections is not None
    finally:
        await close_qdrant_client(client)


@pytest.mark.asyncio
async def test_readiness_endpoint_with_live_services() -> None:
    """Verify GET /api/v1/health/ready returns 200 OK against live services."""
    settings = get_settings()
    test_app = create_app()

    engine = create_database_engine(settings)
    redis_cli = create_redis_client(settings)
    qdrant_cli = create_qdrant_client(settings)

    test_app.state.db_engine = engine
    test_app.state.db_session_factory = create_session_factory(engine)
    test_app.state.redis_client = redis_cli
    test_app.state.qdrant_client = qdrant_cli

    try:
        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://testserver",
        ) as ac:
            res = await ac.get("/api/v1/health/ready")
            assert res.status_code == 200
            body = res.json()
            assert body["status"] == "ok"
            assert body["dependencies"]["postgresql"] == "ok"
            assert body["dependencies"]["redis"] == "ok"
            assert body["dependencies"]["qdrant"] == "ok"
    finally:
        await close_redis_client(redis_cli)
        await close_qdrant_client(qdrant_cli)
        await dispose_database_engine(engine)

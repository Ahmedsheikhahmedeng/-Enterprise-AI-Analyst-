"""E2E test fixtures, authenticated clients, and mock-safe test environments."""

import uuid
from collections.abc import AsyncGenerator, AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.db.postgres import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from app.main import create_app


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        yield session
        await session.rollback()

    await dispose_database_engine(engine)


@pytest.fixture
def test_tenant_id() -> str:
    return "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def other_tenant_id() -> str:
    return "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def admin_headers(test_tenant_id: str) -> dict[str, str]:
    user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    token = create_access_token(
        user_id=user_id,
        extra_claims={
            "email": "admin@enterprise.ai",
            "org_id": test_tenant_id,
            "roles": ["admin"],
            "permissions": [
                "organization.manage",
                "organization.read",
                "users.manage",
                "finops.read",
                "finops.manage",
                "sre.release_gate.read",
            ],
        },
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": test_tenant_id,
        "X-Request-ID": str(uuid.uuid4()),
    }


@pytest.fixture
def analyst_headers(test_tenant_id: str) -> dict[str, str]:
    user_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    token = create_access_token(
        user_id=user_id,
        extra_claims={
            "email": "analyst@enterprise.ai",
            "org_id": test_tenant_id,
            "roles": ["analyst"],
            "permissions": [
                "organization.read",
                "documents.read",
                "datasets.read",
                "rag.query",
                "sql.query",
                "finops.read",
            ],
        },
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": test_tenant_id,
        "X-Request-ID": str(uuid.uuid4()),
    }


@pytest.fixture
def viewer_headers(test_tenant_id: str) -> dict[str, str]:
    user_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    token = create_access_token(
        user_id=user_id,
        extra_claims={
            "email": "viewer@enterprise.ai",
            "org_id": test_tenant_id,
            "roles": ["viewer"],
            "permissions": ["organization.read", "documents.read"],
        },
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": test_tenant_id,
        "X-Request-ID": str(uuid.uuid4()),
    }


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    await dispose_database_engine(engine)

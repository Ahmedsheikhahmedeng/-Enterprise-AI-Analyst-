"""Integration tests for Enterprise Platform Ask API, SSE Streaming, and Executions — TASK 34."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.core.config import get_settings
from app.db.postgres import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from app.main import create_app
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.user import User
from app.rbac.catalog import ROLE_ADMIN
from app.rbac.service import RBACService


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient wired to FastAPI app with PostgreSQL state."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await dispose_database_engine(engine)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide clean database session."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        yield session
    await dispose_database_engine(engine)


async def _setup_admin_tenant(
    session: AsyncSession,
) -> tuple[Organization, User, str, dict[str, str]]:
    """Helper to seed system RBAC and setup an Admin user with auth headers."""
    rbac_svc = RBACService()
    await rbac_svc.seed_system_rbac(session)

    uid = uuid.uuid4().hex[:8]
    org = Organization(name=f"Platform Org {uid}", slug=f"platform-org-{uid}", is_active=True)
    session.add(org)
    await session.flush()

    user = User(
        email=f"platform_admin_{uid}@example.com",
        password_hash=hash_password("Password123!"),
        first_name="Platform",
        last_name="Admin",
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()

    admin_role = (
        await session.execute(
            select(Role).where(Role.name == ROLE_ADMIN, Role.organization_id.is_(None))
        )
    ).scalar_one()

    member = OrganizationMember(organization_id=org.id, user_id=user.id, role_id=admin_role.id)
    session.add(member)
    await session.commit()

    token = create_access_token(user_id=user.id, extra_claims={"email": user.email})
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }
    return org, user, token, headers


@pytest.mark.asyncio
async def test_platform_ask_synchronous_flow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test POST /api/v1/ask with stream=False returning canonical envelope."""
    org, user, token, headers = await _setup_admin_tenant(db_session)

    payload = {
        "question": "What were total sales in 2025?",
        "mode": "AUTO",
        "response_style": "STANDARD",
        "stream": False,
    }

    response = await async_client.post("/api/v1/ask", json=payload, headers=headers)
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["data"] is not None
    assert "execution_id" in body["data"]
    assert "answer" in body["data"]
    assert body["meta"]["request_id"] is not None
    assert body["meta"]["trace_id"] is not None


@pytest.mark.asyncio
async def test_platform_ask_streaming_and_lifecycle(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test full asynchronous streaming lifecycle: ask -> execution_id -> events -> detail -> cancel."""
    org, user, token, headers = await _setup_admin_tenant(db_session)

    # 1. Initiate async execution with stream=True
    ask_payload = {
        "question": "Provide annual strategic revenue breakdown.",
        "mode": "AUTO",
        "stream": True,
    }
    init_res = await async_client.post("/api/v1/ask", json=ask_payload, headers=headers)
    assert init_res.status_code == 200

    init_body = init_res.json()
    assert init_body["success"] is True
    exec_id_str = init_body["data"]["execution_id"]
    assert init_body["data"]["status"] == "RUNNING"
    assert f"/api/v1/ask/{exec_id_str}/stream" in init_body["data"]["stream_url"]

    # 2. Query execution detail
    detail_res = await async_client.get(f"/api/v1/ask/{exec_id_str}", headers=headers)
    assert detail_res.status_code == 200
    detail_body = detail_res.json()
    assert detail_body["success"] is True
    assert detail_body["data"]["id"] == exec_id_str
    assert detail_body["data"]["query"] == ask_payload["question"]

    # 3. Query evidence
    ev_res = await async_client.get(f"/api/v1/ask/{exec_id_str}/evidence", headers=headers)
    assert ev_res.status_code == 200
    assert ev_res.json()["success"] is True
    assert isinstance(ev_res.json()["data"], list)

    # 4. Query provenance
    prov_res = await async_client.get(f"/api/v1/ask/{exec_id_str}/provenance", headers=headers)
    assert prov_res.status_code == 200
    assert prov_res.json()["success"] is True
    assert prov_res.json()["data"]["execution_id"] == exec_id_str

    # 5. Query approval state
    appr_res = await async_client.get(f"/api/v1/ask/{exec_id_str}/approval", headers=headers)
    assert appr_res.status_code == 200
    assert appr_res.json()["success"] is True

    # 6. Replay events
    events_res = await async_client.get(
        f"/api/v1/ask/{exec_id_str}/events?after_sequence=0", headers=headers
    )
    assert events_res.status_code == 200
    events_body = events_res.json()
    assert events_body["success"] is True
    assert "events" in events_body["data"]

    # 7. Cancel execution
    cancel_res = await async_client.post(f"/api/v1/ask/{exec_id_str}/cancel", headers=headers)
    assert cancel_res.status_code == 200
    cancel_body = cancel_res.json()
    assert cancel_body["success"] is True
    assert cancel_body["data"]["current_status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_platform_executions_history(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test GET /api/v1/executions history endpoint with pagination and filters."""
    org, user, token, headers = await _setup_admin_tenant(db_session)

    # Create a couple of executions
    for q in ["First query", "Second query"]:
        await async_client.post(
            "/api/v1/ask",
            json={"question": q, "stream": False},
            headers=headers,
        )

    # List history
    res = await async_client.get("/api/v1/executions?page=1&page_size=10", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["total"] >= 2
    assert len(body["data"]["items"]) >= 2
    assert all(item["query"] is not None for item in body["data"]["items"])


@pytest.mark.asyncio
async def test_platform_admin_endpoints(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test admin system health, metrics, and global executions view."""
    org, user, token, headers = await _setup_admin_tenant(db_session)

    # Health
    health_res = await async_client.get("/api/v1/admin/system/health", headers=headers)
    assert health_res.status_code == 200
    assert health_res.json()["success"] is True
    assert "subsystems" in health_res.json()["data"]

    # Metrics
    metrics_res = await async_client.get("/api/v1/admin/system/metrics", headers=headers)
    assert metrics_res.status_code == 200
    assert metrics_res.json()["success"] is True

    # Global Executions
    exec_res = await async_client.get("/api/v1/admin/system/executions", headers=headers)
    assert exec_res.status_code == 200
    assert exec_res.json()["success"] is True
    assert "items" in exec_res.json()["data"]

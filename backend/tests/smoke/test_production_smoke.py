"""Production Smoke Test Suite validating end-to-end service readiness and core API flows."""

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
async def smoke_client() -> AsyncGenerator[AsyncClient, None]:
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


async def _setup_smoke_admin(
    session: AsyncSession,
) -> tuple[Organization, User, str, dict[str, str]]:
    """Helper to seed system RBAC and setup an Admin user with auth headers."""
    rbac_svc = RBACService()
    await rbac_svc.seed_system_rbac(session)

    uid = uuid.uuid4().hex[:8]
    org = Organization(name=f"Smoke Org {uid}", slug=f"smoke-org-{uid}", is_active=True)
    session.add(org)
    await session.flush()

    user = User(
        email=f"smoke_admin_{uid}@example.com",
        password_hash=hash_password("Password123!"),
        first_name="Smoke",
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
async def test_smoke_health_and_ready(smoke_client: AsyncClient) -> None:
    """Verify platform health and readiness probes return HTTP 200 with valid metadata."""
    # 1. Platform Liveness
    resp_health = await smoke_client.get("/api/v1/platform/health")
    assert resp_health.status_code == 200
    health_data = resp_health.json()
    assert health_data["success"] is True
    assert health_data["data"]["status"] == "ok"
    assert health_data["data"]["service"] == "enterprise-ai-analyst"

    # 2. Platform Readiness
    resp_ready = await smoke_client.get("/api/v1/platform/ready")
    assert resp_ready.status_code == 200
    ready_data = resp_ready.json()
    assert ready_data["success"] is True
    assert ready_data["data"]["status"] in ("ready", "degraded")


@pytest.mark.asyncio
async def test_smoke_authenticated_ask_and_status(
    smoke_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify core Ask lifecycle: query execution, status lookup, and evidence retrieval."""
    org, user, token, headers = await _setup_smoke_admin(db_session)

    # 1. Ask a question
    ask_payload = {
        "question": "What is our total quarterly revenue for Q3?",
        "stream": False,
        "mode": "AUTO",
        "response_style": "STANDARD",
    }
    resp_ask = await smoke_client.post("/api/v1/ask", json=ask_payload, headers=headers)
    assert resp_ask.status_code == 200
    ask_data = resp_ask.json()
    assert ask_data["success"] is True
    execution_id = ask_data["data"]["execution_id"]
    assert execution_id is not None
    assert ask_data["data"]["answer"] is not None

    # 2. Get execution status
    resp_status = await smoke_client.get(f"/api/v1/ask/{execution_id}", headers=headers)
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    assert status_data["success"] is True
    assert status_data["data"]["id"] == execution_id

    # 3. Get evidence
    resp_evidence = await smoke_client.get(f"/api/v1/ask/{execution_id}/evidence", headers=headers)
    assert resp_evidence.status_code == 200
    evidence_data = resp_evidence.json()
    assert evidence_data["success"] is True
    assert isinstance(evidence_data["data"], list)

    # 4. Check approval state for the execution
    resp_approvals = await smoke_client.get(f"/api/v1/ask/{execution_id}/approval", headers=headers)
    assert resp_approvals.status_code == 200
    approvals_data = resp_approvals.json()
    assert approvals_data["success"] is True

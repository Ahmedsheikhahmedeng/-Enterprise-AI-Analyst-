"""Integration tests for Enterprise Agent Memory and Agent Runtime integration — TASK 25."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.models import AnalystDiagnostics, AnalystResult, AnalystRouteType, UnifiedEvidence
from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.db.postgres import create_database_engine, create_session_factory
from app.main import create_app
from app.memory.models import MemoryItem, MemoryVersion
from app.memory.schemas import MemoryType
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.user import User
from app.rbac.catalog import ROLE_ADMIN
from app.rbac.service import RBACService


@pytest.fixture
async def test_env() -> Any:
    """Set up database engine, session factory, and HTTP test client."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield {
            "app": app,
            "client": client,
            "engine": engine,
            "session_factory": session_factory,
        }

    await engine.dispose()


async def setup_org_and_user(
    session: AsyncSession, role_name: str = ROLE_ADMIN
) -> tuple[Organization, User, str]:
    """Seed test organization, user, role membership, and generate JWT bearer token."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    org = Organization(
        id=org_id,
        name=f"Org-{org_id.hex[:6]}",
        slug=f"org-{org_id.hex[:6]}",
    )
    user = User(
        id=user_id,
        email=f"user-{user_id.hex[:6]}@example.com",
        password_hash="hashed_pw",
        first_name="Test",
        last_name="User",
        is_active=True,
    )
    session.add_all([org, user])
    await session.flush()

    rbac_svc = RBACService()
    await rbac_svc.seed_system_rbac(session)
    role_res = await session.execute(select(Role).where(Role.name == role_name))
    role = role_res.scalar_one()

    membership = OrganizationMember(
        organization_id=org_id,
        user_id=user_id,
        role_id=role.id,
    )
    session.add(membership)
    await session.commit()

    token = create_access_token(
        user_id=user.id,
        extra_claims={"org_id": str(org_id), "role": role_name},
    )
    return org, user, token


@pytest.mark.asyncio
async def test_create_and_get_memory_lifecycle(test_env: Any) -> None:
    """Test declaring a memory item, verifying persistence, and retrieving it."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    # 1. Create memory
    create_res = await client.post(
        "/api/v1/memory",
        json={
            "memory_type": "semantic",
            "content": "Organization prefers European date format DD/MM/YYYY.",
            "summary": "Date format preference",
            "importance": 0.8,
            "confidence": 0.95,
        },
        headers=headers,
    )
    assert create_res.status_code == 201, create_res.text
    created = create_res.json()
    memory_id = created["id"]
    assert created["memory_type"] == "semantic"
    assert created["version"] == 1
    assert created["status"] == "active"
    assert created["organization_id"] == str(org.id)

    # 2. Get memory by ID
    get_res = await client.get(f"/api/v1/memory/{memory_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == memory_id
    assert "European date format" in get_res.json()["content"]


@pytest.mark.asyncio
async def test_search_memory_hybrid(test_env: Any) -> None:
    """Test searching memories semantically with calculated relevance scores."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    # Seed 2 memories
    await client.post(
        "/api/v1/memory",
        json={
            "memory_type": "semantic",
            "content": "Customer prefers quarterly revenue summaries in PDF format.",
            "importance": 0.85,
        },
        headers=headers,
    )
    await client.post(
        "/api/v1/memory",
        json={
            "memory_type": "episodic",
            "content": "Invoice batch INV-2024-001 was approved by Finance.",
            "importance": 0.70,
        },
        headers=headers,
    )

    search_res = await client.post(
        "/api/v1/memory/search",
        json={"query": "revenue summaries", "top_k": 5},
        headers=headers,
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total_found"] >= 1
    assert len(search_data["results"]) >= 1
    top_hit = search_data["results"][0]
    assert "relevance_score" in top_hit
    assert "score_breakdown" in top_hit
    assert "quarterly revenue" in top_hit["memory"]["content"].lower()


@pytest.mark.asyncio
async def test_list_and_summary_memory(test_env: Any) -> None:
    """Test paginated memory listing and high-level summary counts."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    await client.post(
        "/api/v1/memory",
        json={"memory_type": "semantic", "content": "Fiscal policy uses USD currency."},
        headers=headers,
    )

    # List memories
    list_res = await client.get("/api/v1/memory?page=1&page_size=10", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1

    # Summary
    summary_res = await client.get("/api/v1/memory/summary", headers=headers)
    assert summary_res.status_code == 200
    summary_data = summary_res.json()
    assert summary_data["total_memories"] >= 1
    assert "semantic" in summary_data["by_type"]


@pytest.mark.asyncio
async def test_update_memory_creates_version(test_env: Any) -> None:
    """Test updating a memory item increments its version and records a historical snapshot."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    create_res = await client.post(
        "/api/v1/memory",
        json={"memory_type": "semantic", "content": "Threshold limit is $5,000."},
        headers=headers,
    )
    mem_id = create_res.json()["id"]

    # Patch memory
    update_res = await client.patch(
        f"/api/v1/memory/{mem_id}",
        json={"content": "Threshold limit updated to $10,000."},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["version"] == 2
    assert "10,000" in update_res.json()["content"]

    # Verify versions table
    async with session_factory() as db:
        ver_res = await db.execute(
            select(MemoryVersion).where(MemoryVersion.memory_id == uuid.UUID(mem_id))
        )
        versions = list(ver_res.scalars().all())
        assert len(versions) == 2


@pytest.mark.asyncio
async def test_soft_delete_memory_tombstone(test_env: Any) -> None:
    """Test soft-deleting memory marks status as deleted and excludes from active search."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    create_res = await client.post(
        "/api/v1/memory",
        json={"memory_type": "semantic", "content": "Ephemeral setting to be deleted."},
        headers=headers,
    )
    mem_id = create_res.json()["id"]

    # Delete
    del_res = await client.delete(f"/api/v1/memory/{mem_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Search should no longer return deleted memory
    search_res = await client.post(
        "/api/v1/memory/search",
        json={"query": "Ephemeral setting to be deleted"},
        headers=headers,
    )
    assert search_res.status_code == 200
    assert not any(r["memory"]["id"] == mem_id for r in search_res.json()["results"])


@pytest.mark.asyncio
async def test_agent_session_memory_injection_and_episodic_creation(test_env: Any) -> None:
    """Test that agent runtime injects memory context and captures episodic memory upon completion."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    # 1. Pre-seed a relevant memory
    await client.post(
        "/api/v1/memory",
        json={
            "memory_type": "semantic",
            "content": "Organization policy requires ARR breakdown by geographic region.",
            "importance": 0.9,
        },
        headers=headers,
    )

    # 2. Create and start an agent session
    create_sess_res = await client.post(
        "/api/v1/agents/sessions",
        json={"agent_type": "analyst_agent", "goal": "Analyze ARR by geographic region"},
        headers=headers,
    )
    assert create_sess_res.status_code == 201
    session_id = create_sess_res.json()["id"]

    mock_analyst_result = AnalystResult(
        answer="ARR breakdown: North America 60%, EMEA 40%.",
        route=AnalystRouteType.SQL,
        grounded=True,
        confidence=0.96,
        is_degraded=False,
        evidence=[
            UnifiedEvidence(
                evidence_id="S1",
                source_type="sql",
                title="arr_by_region",
                text="NA: $6M, EMEA: $4M",
                is_calculated=True,
            )
        ],
        citations=[{"citation_id": "S1"}],
        diagnostics=AnalystDiagnostics(total_cost_usd=0.001, branches_executed=1),
    )

    with patch("app.analyst.service.AIAnalystService.ask", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = mock_analyst_result

        start_res = await client.post(
            f"/api/v1/agents/sessions/{session_id}/start",
            headers=headers,
        )
        assert start_res.status_code == 200
        assert start_res.json()["status"] == "completed"

    # 3. Verify episodic memory was recorded from grounded answer
    async with session_factory() as db:
        mem_res = await db.execute(
            select(MemoryItem).where(
                MemoryItem.session_id == uuid.UUID(session_id),
                MemoryItem.memory_type == MemoryType.EPISODIC.value,
            )
        )
        episodic_items = list(mem_res.scalars().all())
        assert len(episodic_items) >= 1
        assert "Analytical finding" in episodic_items[0].content
        assert episodic_items[0].organization_id == org.id

"""Integration tests for Enterprise Agent Runtime & Typed Tool Orchestration."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import AgentCheckpoint, AgentPlan, AgentSession, AgentStep
from app.agents.schemas import AgentType
from app.agents.service import AgentService
from app.analyst.models import AnalystDiagnostics, AnalystResult, AnalystRouteType, UnifiedEvidence
from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.db.postgres import create_database_engine, create_session_factory
from app.jobs.context import JobContext
from app.jobs.tasks.agent import AgentExecutionTask
from app.main import create_app
from app.models.audit import AuditLog
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
        name=f"Agent Org {org_id.hex[:6]}",
        slug=f"agent-org-{org_id.hex[:6]}",
    )
    session.add(org)

    user = User(
        id=user_id,
        email=f"agent_{user_id.hex[:8]}@example.com",
        first_name="Agent",
        last_name="Tester",
        password_hash="test_hash",
        is_active=True,
    )
    session.add(user)
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
        user_id=user_id,
        extra_claims={"org_id": str(org_id), "role": role_name},
    )
    return org, user, token


@pytest.mark.asyncio
async def test_create_session_and_plan_persisted(test_env: Any) -> None:
    """Test session creation generates validated plan and materializes steps in DB."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    payload = {
        "agent_type": "analyst_agent",
        "goal": "Analyze quarterly enterprise subscription renewals",
        "max_steps": 10,
    }

    resp = await client.post("/api/v1/agents/sessions", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "planned"
    assert body["agent_type"] == "analyst_agent"
    assert body["goal"] == payload["goal"]
    session_id = uuid.UUID(body["id"])

    # Verify persistence in database
    async with session_factory() as db:
        saved_session = await db.get(AgentSession, session_id)
        assert saved_session is not None
        assert saved_session.status == "planned"
        assert saved_session.plan_id is not None

        plan = await db.get(AgentPlan, saved_session.plan_id)
        assert plan is not None
        assert len(plan.steps) > 0

        steps_res = await db.execute(select(AgentStep).where(AgentStep.session_id == session_id))
        steps = steps_res.scalars().all()
        assert len(steps) == len(plan.steps)

        audit_res = await db.execute(
            select(AuditLog).where(
                AuditLog.resource_id == str(session_id),
                AuditLog.action == "agent.session_created",
            )
        )
        assert audit_res.scalars().first() is not None


@pytest.mark.asyncio
async def test_get_session_plan_and_steps(test_env: Any) -> None:
    """Test retrieving session details, generated plan, and materialized steps."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    # 1. Create session
    create_res = await client.post(
        "/api/v1/agents/sessions",
        json={"agent_type": "analyst_agent", "goal": "Inspect sales churn trends"},
        headers=headers,
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["id"]

    # 2. Get session
    get_res = await client.get(f"/api/v1/agents/sessions/{session_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == session_id

    # 3. Get plan
    plan_res = await client.get(f"/api/v1/agents/sessions/{session_id}/plan", headers=headers)
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    assert plan_data["session_id"] == session_id
    assert len(plan_data["steps"]) > 0

    # 4. Get steps
    steps_res = await client.get(f"/api/v1/agents/sessions/{session_id}/steps", headers=headers)
    assert steps_res.status_code == 200
    steps_data = steps_res.json()
    assert len(steps_data) == len(plan_data["steps"])
    assert steps_data[0]["sequence"] == 1


@pytest.mark.asyncio
async def test_execute_agent_session_analyst_tool(test_env: Any) -> None:
    """Test executing session end-to-end with AnalystTool, creating checkpoints and provenance."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    create_res = await client.post(
        "/api/v1/agents/sessions",
        json={"agent_type": "analyst_agent", "goal": "Explain revenue growth"},
        headers=headers,
    )
    session_id = create_res.json()["id"]

    mock_analyst_result = AnalystResult(
        answer="Revenue increased by 15% due to enterprise expansions.",
        route=AnalystRouteType.SQL,
        grounded=True,
        confidence=0.95,
        is_degraded=False,
        evidence=[
            UnifiedEvidence(
                evidence_id="S1",
                source_type="sql",
                title="revenue_summary",
                text="Q3 revenue: $4.2M (+15% YoY)",
                is_calculated=True,
            )
        ],
        citations=[{"citation_id": "S1"}],
        diagnostics=AnalystDiagnostics(total_cost_usd=0.002, branches_executed=1),
    )

    with patch("app.analyst.service.AIAnalystService.ask", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = mock_analyst_result

        start_res = await client.post(
            f"/api/v1/agents/sessions/{session_id}/start", headers=headers
        )
        assert start_res.status_code == 200, start_res.text
        res_data = start_res.json()
        assert res_data["status"] == "completed"
        assert "S1" in res_data["citations"]
        assert res_data["grounded"] is True

    # Verify Checkpoint persisted in database
    async with session_factory() as db:
        cp_res = await db.execute(
            select(AgentCheckpoint).where(AgentCheckpoint.session_id == uuid.UUID(session_id))
        )
        checkpoints = cp_res.scalars().all()
        assert len(checkpoints) >= 1
        assert checkpoints[0].status == "completed"
        assert "S1" in checkpoints[0].evidence_ids


@pytest.mark.asyncio
async def test_approval_gate_flow_pause_approve_resume(test_env: Any) -> None:
    """Test approval flow: execution pauses on sensitive tool, operator approves, session resumes."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    # Create report agent session (which has report.create requiring approval)
    create_res = await client.post(
        "/api/v1/agents/sessions",
        json={"agent_type": "report_agent", "goal": "Publish monthly executive overview"},
        headers=headers,
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["id"]

    mock_analyst_result = AnalystResult(
        answer="Executive overview metrics compiled.",
        route=AnalystRouteType.SQL,
        grounded=True,
        confidence=0.92,
        evidence=[
            UnifiedEvidence(
                evidence_id="S1",
                source_type="sql",
                title="kpi",
                text="ARR reached $12M",
                is_calculated=True,
            )
        ],
        citations=[{"citation_id": "S1"}],
        diagnostics=AnalystDiagnostics(total_cost_usd=0.002, branches_executed=1),
    )

    with patch("app.analyst.service.AIAnalystService.ask", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = mock_analyst_result

        # Start execution: Step 1 (analyst.query) executes, Step 2 (report.create) triggers approval gate
        start_res = await client.post(
            f"/api/v1/agents/sessions/{session_id}/start", headers=headers
        )
        assert start_res.status_code == 200
        start_data = start_res.json()
        assert start_data["status"] == "awaiting_approval"

    # List approvals
    app_res = await client.get(f"/api/v1/agents/sessions/{session_id}/approvals", headers=headers)
    assert app_res.status_code == 200
    approvals = app_res.json()
    assert len(approvals) == 1
    approval_id = approvals[0]["id"]
    assert approvals[0]["status"] == "pending"

    # Approve request
    approve_res = await client.post(
        f"/api/v1/agents/sessions/{session_id}/approvals/{approval_id}/approve",
        json={"reason": "Executive sign-off confirmed by admin"},
        headers=headers,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"

    # Mock report service for step 2
    mock_report = AsyncMock()
    mock_report.id = uuid.uuid4()
    mock_report.title = "Monthly Executive Overview"
    mock_report.status = "published"
    mock_version = AsyncMock()
    mock_version.id = uuid.uuid4()
    mock_doc = AsyncMock()
    mock_doc.executive_summary = "Monthly overview summary"

    with patch(
        "app.reports.service.ReportService.create_report_from_analysis", new_callable=AsyncMock
    ) as mock_create_rep:
        mock_create_rep.return_value = (mock_report, mock_version, mock_doc)

        # Resume session
        resume_res = await client.post(
            f"/api/v1/agents/sessions/{session_id}/resume", headers=headers
        )
        assert resume_res.status_code == 200
        resume_data = resume_res.json()
        assert resume_data["status"] == "completed"


@pytest.mark.asyncio
async def test_approval_reject_flow(test_env: Any) -> None:
    """Test operator rejecting an approval gate."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    create_res = await client.post(
        "/api/v1/agents/sessions",
        json={"agent_type": "report_agent", "goal": "Publish unvetted financial summary"},
        headers=headers,
    )
    session_id = create_res.json()["id"]

    mock_analyst_result = AnalystResult(
        answer="Summary data retrieved.",
        route=AnalystRouteType.SQL,
        grounded=True,
        confidence=0.90,
        evidence=[
            UnifiedEvidence(
                evidence_id="S1",
                source_type="sql",
                title="summary_kpi",
                text="Summary text",
                is_calculated=True,
            )
        ],
        citations=[{"citation_id": "S1"}],
        diagnostics=AnalystDiagnostics(total_cost_usd=0.001, branches_executed=1),
    )

    # Trigger approval request
    with patch("app.analyst.service.AIAnalystService.ask", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = mock_analyst_result
        await client.post(f"/api/v1/agents/sessions/{session_id}/start", headers=headers)

    app_res = await client.get(f"/api/v1/agents/sessions/{session_id}/approvals", headers=headers)
    approval_id = app_res.json()[0]["id"]

    reject_res = await client.post(
        f"/api/v1/agents/sessions/{session_id}/approvals/{approval_id}/reject",
        json={"reason": "Data not audited yet"},
        headers=headers,
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_cancel_agent_session(test_env: Any) -> None:
    """Test cancelling an active or planned agent session."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    create_res = await client.post(
        "/api/v1/agents/sessions",
        json={"agent_type": "analyst_agent", "goal": "Long running analysis to be cancelled"},
        headers=headers,
    )
    session_id = create_res.json()["id"]

    cancel_res = await client.post(f"/api/v1/agents/sessions/{session_id}/cancel", headers=headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # Verify cancelled status and timestamp in DB
    async with session_factory() as db:
        sess = await db.get(AgentSession, uuid.UUID(session_id))
        assert sess is not None
        assert sess.status == "cancelled"
        assert sess.cancelled_at is not None


@pytest.mark.asyncio
async def test_worker_agent_execution_job(test_env: Any) -> None:
    """Test executing an AgentSession asynchronously through background worker task."""
    session_factory = test_env["session_factory"]

    async with session_factory() as db:
        org, user, token = await setup_org_and_user(db, role_name=ROLE_ADMIN)

        service = AgentService()
        from app.agents.schemas import AgentSessionCreateRequest

        sess, plan = await service.create_session(
            db_session=db,
            organization_id=org.id,
            req=AgentSessionCreateRequest(
                agent_type=AgentType.ANALYST_AGENT,
                goal="Worker background task execution test",
            ),
            user_id=user.id,
        )
        session_id = sess.id

    mock_analyst_result = AnalystResult(
        answer="Worker background execution completed successfully.",
        route=AnalystRouteType.SQL,
        grounded=True,
        confidence=0.98,
        evidence=[
            UnifiedEvidence(
                evidence_id="S1",
                source_type="sql",
                title="worker_kpi",
                text="Worker job success",
                is_calculated=True,
            )
        ],
        citations=[{"citation_id": "S1"}],
        diagnostics=AnalystDiagnostics(total_cost_usd=0.001, branches_executed=1),
    )

    with patch("app.analyst.service.AIAnalystService.ask", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = mock_analyst_result

        task_handler = AgentExecutionTask()
        task_handler.session_factory = session_factory
        job_ctx = JobContext(
            job_id=uuid.uuid4(),
            organization_id=org.id,
            job_type="agent_execution",
            attempt=1,
            max_attempts=3,
            created_by=user.id,
            trace_id="trace-worker-agent-1",
        )

        result = await task_handler.run(payload={"session_id": str(session_id)}, context=job_ctx)
        assert result["status"] == "completed"
        assert "S1" in result["citations"]

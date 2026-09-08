"""Integration tests for Enterprise Governance, Human-in-the-Loop workflow, and Pre-Execution gates."""

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
from app.governance.application.approval_service import ApprovalService
from app.governance.application.decision_service import DecisionService
from app.governance.application.governance_service import GovernanceService
from app.governance.application.policy_service import PolicyService
from app.governance.application.review_service import ReviewService
from app.governance.application.risk_service import RiskService
from app.governance.domain.enums import ApprovalStatus, ApprovalType, RiskLevel, VoteDecision
from app.governance.domain.errors import (
    ApprovalRevokedError,
    PreExecutionBlockedError,
    SelfApprovalError,
    TOCTOUMismatchError,
)
from app.governance.infrastructure.repository import GovernanceRepository
from app.main import create_app
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.user import User
from app.rbac.catalog import ROLE_ADMIN, ROLE_ANALYST
from app.rbac.service import RBACService


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide real PostgreSQL session with automatic rollback."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        yield session
    await dispose_database_engine(engine)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient wired to FastAPI app."""
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


async def _setup_org_and_users(session: AsyncSession) -> tuple[Organization, User, User, User]:
    """Create test organization and three users (requester, approver1, approver2)."""
    rbac_svc = RBACService()
    await rbac_svc.seed_system_rbac(session)

    uid = uuid.uuid4().hex[:8]
    org = Organization(name=f"Gov Org {uid}", slug=f"gov-org-{uid}", is_active=True)
    session.add(org)
    await session.flush()

    admin_res = await session.execute(
        select(Role).where(Role.name == ROLE_ADMIN, Role.organization_id.is_(None))
    )
    admin_role = admin_res.scalars().first()
    analyst_res = await session.execute(
        select(Role).where(Role.name == ROLE_ANALYST, Role.organization_id.is_(None))
    )
    analyst_role = analyst_res.scalars().first()
    assert admin_role is not None and analyst_role is not None

    def _make_user(prefix: str) -> User:
        return User(
            email=f"{prefix}_{uid}@example.com",
            password_hash=hash_password("Password123!"),
            first_name=prefix,
            last_name="Test",
            is_active=True,
            is_verified=True,
        )

    requester = _make_user("requester")
    approver1 = _make_user("approver1")
    approver2 = _make_user("approver2")
    session.add_all([requester, approver1, approver2])
    await session.flush()

    # Add memberships: requester is Analyst, approver1 & 2 are Admin
    session.add(
        OrganizationMember(organization_id=org.id, user_id=requester.id, role_id=analyst_role.id)
    )
    session.add(
        OrganizationMember(organization_id=org.id, user_id=approver1.id, role_id=admin_role.id)
    )
    session.add(
        OrganizationMember(organization_id=org.id, user_id=approver2.id, role_id=admin_role.id)
    )
    await session.commit()

    return org, requester, approver1, approver2


@pytest.mark.asyncio
async def test_end_to_end_governance_lifecycle(db_session: AsyncSession) -> None:
    """Full lifecycle: create request -> review comment -> approve -> pre-execution verify & TOCTOU."""
    org, requester, approver1, _ = await _setup_org_and_users(db_session)

    repo = GovernanceRepository(db_session)
    risk_svc = RiskService()
    policy_svc = PolicyService(repo)
    decision_svc = DecisionService(repo)
    approval_svc = ApprovalService(repo, risk_svc, policy_svc, decision_svc)
    review_svc = ReviewService(repo)
    gov_svc = GovernanceService(repo, approval_svc, risk_svc, policy_svc)

    action_payload = {"sql": "SELECT * FROM payroll_records", "export_format": "csv"}

    # 1. Create HIGH-risk approval request
    req = await approval_svc.create_approval_request(
        organization_id=org.id,
        requester_id=requester.id,
        request_type=ApprovalType.DATA_EXPORT,
        resource_type="DATASET",
        resource_id="payroll_records",
        action_payload=action_payload,
        reason="Quarterly payroll audit",
        risk_factors={"row_count": 5000, "data_sensitivity": "CONFIDENTIAL"},
    )
    assert req.status == ApprovalStatus.PENDING
    assert req.risk_level == RiskLevel.HIGH
    assert req.action_hash is not None
    assert req.resource_hash is not None

    # 2. Separation of duties: Requester cannot self-approve
    with pytest.raises(SelfApprovalError):
        await approval_svc.cast_vote(
            organization_id=org.id,
            request_id=req.id,
            reviewer_id=requester.id,
            decision=VoteDecision.APPROVE,
        )

    # 3. Add reviewer comment
    comment = await review_svc.add_comment(
        organization_id=org.id,
        request_id=req.id,
        author_id=approver1.id,
        comment="Checking compliance with HR data export policy",
    )
    assert comment.comment == "Checking compliance with HR data export policy"

    # 4. Approver 1 approves request
    approved_req, quorum = await approval_svc.cast_vote(
        organization_id=org.id,
        request_id=req.id,
        reviewer_id=approver1.id,
        decision=VoteDecision.APPROVE,
        comment="Approved for compliance audit",
    )
    assert quorum.is_reached is True
    assert approved_req.status == ApprovalStatus.APPROVED

    # 5. Verify immutable decision record
    decision = await decision_svc.get_decision(org.id, req.id)
    assert decision is not None
    assert decision.decision == ApprovalStatus.APPROVED
    assert str(approver1.id) in decision.reviewer_ids
    assert len(decision.decision_hash) == 64

    # 6. Pre-Execution Gate: Authorized with identical payload
    authorized = await gov_svc.verify_pre_execution_gate(
        approval_id=req.id,
        organization_id=org.id,
        current_action_payload=action_payload,
        resource_type="DATASET",
        resource_id="payroll_records",
    )
    assert authorized is True

    # 7. TOCTOU Protection: Tampered payload is rejected
    tampered_payload = {"sql": "SELECT * FROM users", "export_format": "csv"}
    with pytest.raises(TOCTOUMismatchError):
        await gov_svc.verify_pre_execution_gate(
            approval_id=req.id,
            organization_id=org.id,
            current_action_payload=tampered_payload,
            resource_type="DATASET",
            resource_id="payroll_records",
        )


@pytest.mark.asyncio
async def test_multi_approver_critical_workflow(db_session: AsyncSession) -> None:
    """CRITICAL actions mandate two distinct approvers (two-person rule)."""
    org, requester, approver1, approver2 = await _setup_org_and_users(db_session)

    repo = GovernanceRepository(db_session)
    risk_svc = RiskService()
    policy_svc = PolicyService(repo)
    decision_svc = DecisionService(repo)
    approval_svc = ApprovalService(repo, risk_svc, policy_svc, decision_svc)
    gov_svc = GovernanceService(repo, approval_svc, risk_svc, policy_svc)

    # CRITICAL request: External side effect
    crit_payload = {"action": "delete_customer_account", "customer_id": "cust-999"}
    req = await approval_svc.create_approval_request(
        organization_id=org.id,
        requester_id=requester.id,
        request_type=ApprovalType.AGENT_HIGH_RISK_ACTION,
        resource_type="SYSTEM",
        resource_id="customer_service",
        action_payload=crit_payload,
        risk_factors={"external_side_effect": True, "operation_name": "delete_external"},
    )
    assert req.risk_level == RiskLevel.CRITICAL
    assert req.status == ApprovalStatus.PENDING

    # Reviewer 1 votes APPROVE -> Status is IN_REVIEW, quorum (2) NOT reached
    updated_1, quorum_1 = await approval_svc.cast_vote(
        organization_id=org.id,
        request_id=req.id,
        reviewer_id=approver1.id,
        decision=VoteDecision.APPROVE,
    )
    assert updated_1.status == ApprovalStatus.IN_REVIEW
    assert quorum_1.is_reached is False

    # Pre-execution gate must block while awaiting second approver
    with pytest.raises(PreExecutionBlockedError):
        await gov_svc.verify_pre_execution_gate(
            approval_id=req.id,
            organization_id=org.id,
            current_action_payload=crit_payload,
            resource_type="SYSTEM",
            resource_id="customer_service",
        )

    # Reviewer 2 votes APPROVE -> Quorum reached, status APPROVED
    updated_2, quorum_2 = await approval_svc.cast_vote(
        organization_id=org.id,
        request_id=req.id,
        reviewer_id=approver2.id,
        decision=VoteDecision.APPROVE,
    )
    assert quorum_2.is_reached is True
    assert updated_2.status == ApprovalStatus.APPROVED

    # Now Pre-execution gate succeeds
    assert (
        await gov_svc.verify_pre_execution_gate(
            approval_id=req.id,
            organization_id=org.id,
            current_action_payload=crit_payload,
            resource_type="SYSTEM",
            resource_id="customer_service",
        )
        is True
    )


@pytest.mark.asyncio
async def test_rejection_and_revocation_lifecycle(db_session: AsyncSession) -> None:
    """Test approval revocation and rejection flows."""
    org, requester, approver1, _ = await _setup_org_and_users(db_session)

    repo = GovernanceRepository(db_session)
    risk_svc = RiskService()
    policy_svc = PolicyService(repo)
    decision_svc = DecisionService(repo)
    approval_svc = ApprovalService(repo, risk_svc, policy_svc, decision_svc)
    gov_svc = GovernanceService(repo, approval_svc, risk_svc, policy_svc)

    payload = {"query": "SELECT * FROM sales"}
    req = await approval_svc.create_approval_request(
        organization_id=org.id,
        requester_id=requester.id,
        request_type=ApprovalType.QUERY_EXECUTION,
        resource_type="DATASET",
        resource_id="sales",
        action_payload=payload,
        risk_factors={"data_sensitivity": "SENSITIVE"},
    )

    # Approve
    await approval_svc.cast_vote(
        organization_id=org.id,
        request_id=req.id,
        reviewer_id=approver1.id,
        decision=VoteDecision.APPROVE,
    )

    # Revoke before execution
    revoked = await approval_svc.revoke_approval(
        organization_id=org.id,
        request_id=req.id,
        revoker_id=approver1.id,
        reason="Security audit flag raised",
    )
    assert revoked.status == ApprovalStatus.REVOKED

    # Pre-execution gate must block revoked request
    with pytest.raises(ApprovalRevokedError):
        await gov_svc.verify_pre_execution_gate(
            approval_id=req.id,
            organization_id=org.id,
            current_action_payload=payload,
            resource_type="DATASET",
            resource_id="sales",
        )


@pytest.mark.asyncio
async def test_automatic_approval_flow(db_session: AsyncSession) -> None:
    """LOW risk operations pass automatically with immediate immutable decision sealing."""
    org, requester, _, _ = await _setup_org_and_users(db_session)

    repo = GovernanceRepository(db_session)
    risk_svc = RiskService()
    policy_svc = PolicyService(repo)
    decision_svc = DecisionService(repo)
    approval_svc = ApprovalService(repo, risk_svc, policy_svc, decision_svc)
    gov_svc = GovernanceService(repo, approval_svc, risk_svc, policy_svc)

    payload = {"query": "SELECT id FROM catalog_items LIMIT 10"}
    req = await approval_svc.create_approval_request(
        organization_id=org.id,
        requester_id=requester.id,
        request_type=ApprovalType.QUERY_EXECUTION,
        resource_type="DATASET",
        resource_id="catalog_items",
        action_payload=payload,
        risk_factors={"data_sensitivity": "PUBLIC", "row_count": 10},
    )

    # Should be immediately approved
    assert req.status == ApprovalStatus.APPROVED
    assert req.risk_level == RiskLevel.LOW

    # Decision sealed with SYSTEM_AUTO_APPROVER
    decision = await decision_svc.get_decision(org.id, req.id)
    assert decision is not None
    assert "SYSTEM_AUTO_APPROVER" in decision.reviewer_ids

    # Gate succeeds immediately
    assert (
        await gov_svc.verify_pre_execution_gate(
            approval_id=req.id,
            organization_id=org.id,
            current_action_payload=payload,
            resource_type="DATASET",
            resource_id="catalog_items",
        )
        is True
    )


@pytest.mark.asyncio
async def test_governance_api_endpoints(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test full HTTP REST API endpoints under /api/v1/governance."""
    org, requester, approver1, _ = await _setup_org_and_users(db_session)

    # Issue tokens
    req_token = create_access_token(user_id=requester.id, extra_claims={"org_id": str(org.id)})
    app_token = create_access_token(user_id=approver1.id, extra_claims={"org_id": str(org.id)})

    req_headers = {"Authorization": f"Bearer {req_token}", "X-Organization-ID": str(org.id)}
    app_headers = {"Authorization": f"Bearer {app_token}", "X-Organization-ID": str(org.id)}

    # 1. POST /api/v1/governance/approvals
    create_res = await async_client.post(
        "/api/v1/governance/approvals",
        json={
            "request_type": "DATA_EXPORT",
            "resource_type": "DATASET",
            "resource_id": "customers",
            "action_payload": {"format": "csv"},
            "reason": "Exporting customer lists",
            "risk_factors": {"row_count": 5000, "data_sensitivity": "CONFIDENTIAL"},
        },
        headers=req_headers,
    )
    assert create_res.status_code == 201
    approval_data = create_res.json()
    approval_id = approval_data["id"]
    assert approval_data["status"] == "PENDING"
    assert approval_data["risk_level"] == "HIGH"

    # 2. GET /api/v1/governance/approvals
    list_res = await async_client.get("/api/v1/governance/approvals", headers=app_headers)
    assert list_res.status_code == 200
    assert any(a["id"] == approval_id for a in list_res.json())

    # 3. GET /api/v1/governance/requests/high-risk
    hr_res = await async_client.get("/api/v1/governance/requests/high-risk", headers=app_headers)
    assert hr_res.status_code == 200
    assert any(a["id"] == approval_id for a in hr_res.json())

    # 4. POST /api/v1/governance/approvals/{id}/review
    comment_res = await async_client.post(
        f"/api/v1/governance/approvals/{approval_id}/review",
        json={"comment": "Reviewing data classification"},
        headers=app_headers,
    )
    assert comment_res.status_code == 200
    assert comment_res.json()["comment"] == "Reviewing data classification"

    # 5. POST /api/v1/governance/approvals/{id}/approve
    approve_res = await async_client.post(
        f"/api/v1/governance/approvals/{approval_id}/approve",
        json={"comment": "Looks good to export"},
        headers=app_headers,
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # 6. GET /api/v1/governance/{id}/history
    hist_res = await async_client.get(
        f"/api/v1/governance/{approval_id}/history",
        headers=app_headers,
    )
    assert hist_res.status_code == 200
    assert hist_res.json()["decision"] == "APPROVED"
    assert len(hist_res.json()["decision_hash"]) == 64

    # 7. GET /api/v1/governance/policies
    pol_res = await async_client.get("/api/v1/governance/policies", headers=app_headers)
    assert pol_res.status_code == 200
    assert pol_res.json()["policy_version"] >= 1

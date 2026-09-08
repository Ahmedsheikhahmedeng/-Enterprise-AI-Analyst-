"""Security tests verifying tenant isolation, separation of duties, TOCTOU protection, and quorum integrity."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.governance.application.approval_service import ApprovalService
from app.governance.application.decision_service import (
    DecisionService,
    compute_action_hash,
    compute_resource_hash,
)
from app.governance.application.governance_service import GovernanceService
from app.governance.application.policy_service import DEFAULT_GOVERNANCE_RULES, PolicyService
from app.governance.application.risk_service import RiskService
from app.governance.domain.enums import ApprovalStatus, ApprovalType, RiskLevel, VoteDecision
from app.governance.domain.errors import (
    ApprovalExpiredError,
    ApprovalNotFoundError,
    ApprovalRevokedError,
    PreExecutionBlockedError,
    SelfApprovalError,
    TOCTOUMismatchError,
)
from app.governance.domain.models import ApprovalRequest


@pytest.fixture
def mock_governance_env() -> tuple[ApprovalService, GovernanceService, AsyncMock]:
    """Fixture providing mocked repository and services for governance security testing."""
    repo = AsyncMock()
    risk_svc = RiskService()
    policy_svc = PolicyService(repo)
    decision_svc = DecisionService(repo)
    approval_svc = ApprovalService(repo, risk_svc, policy_svc, decision_svc)
    gov_svc = GovernanceService(repo, approval_svc, risk_svc, policy_svc)

    # Setup default policy mock
    active_policy = MagicMock()
    active_policy.id = uuid.uuid4()
    active_policy.organization_id = uuid.uuid4()
    active_policy.policy_version = 1
    active_policy.rules = DEFAULT_GOVERNANCE_RULES
    active_policy.status = "ACTIVE"
    active_policy.created_by = None
    active_policy.approved_by = None
    active_policy.created_at = None
    active_policy.updated_at = None
    repo.get_active_policy.return_value = active_policy
    repo.get_policy_by_version.return_value = active_policy

    return approval_svc, gov_svc, repo


@pytest.mark.asyncio
async def test_tenant_isolation_cross_tenant_access_blocked(
    mock_governance_env: tuple[ApprovalService, GovernanceService, AsyncMock],
) -> None:
    """An actor in Org A must not be able to retrieve or vote on an approval belonging to Org B."""
    approval_svc, _, repo = mock_governance_env

    org_a = uuid.uuid4()
    request_id = uuid.uuid4()
    reviewer_org_a = uuid.uuid4()

    # Org B returns None when queried with Org A's ID
    repo.get_request.return_value = None

    with pytest.raises(ApprovalNotFoundError):
        await approval_svc.get_request(organization_id=org_a, request_id=request_id)

    with pytest.raises(ApprovalNotFoundError):
        await approval_svc.cast_vote(
            organization_id=org_a,
            request_id=request_id,
            reviewer_id=reviewer_org_a,
            decision=VoteDecision.APPROVE,
        )


@pytest.mark.asyncio
async def test_separation_of_duties_self_approval_blocked(
    mock_governance_env: tuple[ApprovalService, GovernanceService, AsyncMock],
) -> None:
    """Requester cannot self-approve their own HIGH or CRITICAL request."""
    approval_svc, _, repo = mock_governance_env

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    request_id = uuid.uuid4()

    req_mock = MagicMock()
    req_mock.id = request_id
    req_mock.organization_id = org_id
    req_mock.request_type = ApprovalType.DATA_EXPORT.value
    req_mock.requester_id = user_id  # Same user!
    req_mock.resource_type = "DATASET"
    req_mock.resource_id = "ds-1"
    req_mock.risk_level = RiskLevel.HIGH.value
    req_mock.risk_score = 0.75
    req_mock.status = ApprovalStatus.PENDING.value
    req_mock.reason = "Export sensitive data"
    req_mock.context = {}
    req_mock.policy_version = 1
    req_mock.expires_at = datetime.now(UTC) + timedelta(hours=2)

    repo.get_request.return_value = req_mock

    with pytest.raises(SelfApprovalError) as exc:
        await approval_svc.cast_vote(
            organization_id=org_id,
            request_id=request_id,
            reviewer_id=user_id,  # Requester attempts to approve self
            decision=VoteDecision.APPROVE,
        )
    assert "Separation of duties violation" in str(exc.value)


@pytest.mark.asyncio
async def test_separation_of_duties_agent_self_approval_blocked(
    mock_governance_env: tuple[ApprovalService, GovernanceService, AsyncMock],
) -> None:
    """An autonomous AI Agent cannot approve its own request."""
    approval_svc, _, repo = mock_governance_env

    org_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    request_id = uuid.uuid4()

    req_mock = MagicMock()
    req_mock.id = request_id
    req_mock.organization_id = org_id
    req_mock.request_type = ApprovalType.AGENT_HIGH_RISK_ACTION.value
    req_mock.requester_id = agent_id
    req_mock.resource_type = "TOOL"
    req_mock.resource_id = "db_drop"
    req_mock.risk_level = RiskLevel.CRITICAL.value
    req_mock.risk_score = 0.95
    req_mock.status = ApprovalStatus.PENDING.value
    req_mock.reason = "Agent step execution"
    req_mock.context = {"is_agent": True}
    req_mock.policy_version = 1
    req_mock.expires_at = datetime.now(UTC) + timedelta(hours=2)

    repo.get_request.return_value = req_mock

    with pytest.raises(SelfApprovalError) as exc:
        await approval_svc.cast_vote(
            organization_id=org_id,
            request_id=request_id,
            reviewer_id=agent_id,
            decision=VoteDecision.APPROVE,
        )
    assert "cannot approve" in str(exc.value)


@pytest.mark.asyncio
async def test_toctou_action_hash_mutation_blocked(
    mock_governance_env: tuple[ApprovalService, GovernanceService, AsyncMock],
) -> None:
    """Pre-execution gate must block execution if the action payload changed after approval."""
    approval_svc, gov_svc, _ = mock_governance_env

    approved_payload = {"sql": "SELECT id, name FROM customers", "limit": 100}
    tampered_payload = {"sql": "SELECT id, name, credit_card_num FROM customers", "limit": 100}

    approved_hash = compute_action_hash(approved_payload)
    resource_hash = compute_resource_hash("DATASET", "customers")

    approved_request = ApprovalRequest(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        request_type=ApprovalType.QUERY_EXECUTION,
        requester_id=uuid.uuid4(),
        resource_type="DATASET",
        resource_id="customers",
        risk_level=RiskLevel.MEDIUM,
        risk_score=0.45,
        status=ApprovalStatus.APPROVED,
        reason="Query access",
        context={},
        action_hash=approved_hash,
        resource_hash=resource_hash,
        policy_version=1,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    approval_svc.get_request = AsyncMock(return_value=approved_request)  # type: ignore[method-assign]

    with pytest.raises(TOCTOUMismatchError) as exc:
        await gov_svc.verify_pre_execution_gate(
            approval_id=approved_request.id,
            organization_id=approved_request.organization_id,
            current_action_payload=tampered_payload,  # Tampered!
            resource_type="DATASET",
            resource_id="customers",
        )
    assert "parameters were modified" in str(exc.value)


@pytest.mark.asyncio
async def test_toctou_resource_hash_mutation_blocked(
    mock_governance_env: tuple[ApprovalService, GovernanceService, AsyncMock],
) -> None:
    """Pre-execution gate must block execution if the target resource changed after approval."""
    approval_svc, gov_svc, _ = mock_governance_env

    payload = {"rows": 1000}
    approved_hash = compute_action_hash(payload)
    approved_res_hash = compute_resource_hash("DATASET", "dataset_public_1")

    approved_request = ApprovalRequest(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        request_type=ApprovalType.DATA_ACCESS,
        requester_id=uuid.uuid4(),
        resource_type="DATASET",
        resource_id="dataset_public_1",
        risk_level=RiskLevel.LOW,
        risk_score=0.15,
        status=ApprovalStatus.APPROVED,
        reason="Dataset access",
        context={},
        action_hash=approved_hash,
        resource_hash=approved_res_hash,
        policy_version=1,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    approval_svc.get_request = AsyncMock(return_value=approved_request)  # type: ignore[method-assign]

    with pytest.raises(TOCTOUMismatchError) as exc:
        await gov_svc.verify_pre_execution_gate(
            approval_id=approved_request.id,
            organization_id=approved_request.organization_id,
            current_action_payload=payload,
            resource_type="DATASET",
            resource_id="dataset_secret_pii",  # Tampered resource!
        )
    assert "target resource was modified" in str(exc.value)


@pytest.mark.asyncio
async def test_expired_approval_execution_blocked(
    mock_governance_env: tuple[ApprovalService, GovernanceService, AsyncMock],
) -> None:
    """Pre-execution gate must reject execution if expires_at has passed."""
    approval_svc, gov_svc, _ = mock_governance_env

    payload = {"export": True}
    a_hash = compute_action_hash(payload)
    r_hash = compute_resource_hash("EXPORT", "exp-1")

    expired_request = ApprovalRequest(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        request_type=ApprovalType.DATA_EXPORT,
        requester_id=uuid.uuid4(),
        resource_type="EXPORT",
        resource_id="exp-1",
        risk_level=RiskLevel.HIGH,
        risk_score=0.75,
        status=ApprovalStatus.APPROVED,
        reason="Export",
        context={},
        action_hash=a_hash,
        resource_hash=r_hash,
        policy_version=1,
        expires_at=datetime.now(UTC) - timedelta(minutes=5),  # Expired!
    )

    approval_svc.get_request = AsyncMock(return_value=expired_request)  # type: ignore[method-assign]

    with pytest.raises(ApprovalExpiredError):
        await gov_svc.verify_pre_execution_gate(
            approval_id=expired_request.id,
            organization_id=expired_request.organization_id,
            current_action_payload=payload,
            resource_type="EXPORT",
            resource_id="exp-1",
        )


@pytest.mark.asyncio
async def test_revoked_approval_execution_blocked(
    mock_governance_env: tuple[ApprovalService, GovernanceService, AsyncMock],
) -> None:
    """Pre-execution gate must reject execution if approval was revoked."""
    approval_svc, gov_svc, _ = mock_governance_env

    payload = {"deploy": True}
    a_hash = compute_action_hash(payload)
    r_hash = compute_resource_hash("MODEL", "gpt-4")

    revoked_request = ApprovalRequest(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        request_type=ApprovalType.MODEL_CHANGE,
        requester_id=uuid.uuid4(),
        resource_type="MODEL",
        resource_id="gpt-4",
        risk_level=RiskLevel.HIGH,
        risk_score=0.75,
        status=ApprovalStatus.REVOKED,
        reason="Deploy model",
        context={},
        action_hash=a_hash,
        resource_hash=r_hash,
        policy_version=1,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    approval_svc.get_request = AsyncMock(return_value=revoked_request)  # type: ignore[method-assign]

    with pytest.raises(ApprovalRevokedError):
        await gov_svc.verify_pre_execution_gate(
            approval_id=revoked_request.id,
            organization_id=revoked_request.organization_id,
            current_action_payload=payload,
            resource_type="MODEL",
            resource_id="gpt-4",
        )


@pytest.mark.asyncio
async def test_unapproved_status_execution_blocked(
    mock_governance_env: tuple[ApprovalService, GovernanceService, AsyncMock],
) -> None:
    """Pre-execution gate blocks actions that are still PENDING or IN_REVIEW."""
    approval_svc, gov_svc, _ = mock_governance_env

    pending_request = ApprovalRequest(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        request_type=ApprovalType.REPORT_PUBLICATION,
        requester_id=uuid.uuid4(),
        resource_type="REPORT",
        resource_id="rep-1",
        risk_level=RiskLevel.HIGH,
        risk_score=0.75,
        status=ApprovalStatus.PENDING,
        reason="Publish report",
        context={},
        action_hash="h1",
        resource_hash="h2",
        policy_version=1,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    approval_svc.get_request = AsyncMock(return_value=pending_request)  # type: ignore[method-assign]

    with pytest.raises(PreExecutionBlockedError):
        await gov_svc.verify_pre_execution_gate(
            approval_id=pending_request.id,
            organization_id=pending_request.organization_id,
            current_action_payload={},
            resource_type="REPORT",
            resource_id="rep-1",
        )

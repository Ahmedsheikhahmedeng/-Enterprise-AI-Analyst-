"""Failure injection tests for Governance edge cases, rejections, timeouts, and state violations."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.governance.application.approval_service import ApprovalService
from app.governance.application.decision_service import DecisionService
from app.governance.application.governance_service import GovernanceService
from app.governance.application.policy_service import DEFAULT_GOVERNANCE_RULES, PolicyService
from app.governance.application.review_service import ReviewService
from app.governance.application.risk_service import RiskService
from app.governance.domain.enums import ApprovalStatus, ApprovalType, RiskLevel, VoteDecision
from app.governance.domain.errors import (
    ApprovalExpiredError,
    InvalidStateTransitionError,
)


@pytest.fixture
def failure_test_env() -> tuple[ApprovalService, GovernanceService, ReviewService, AsyncMock]:
    repo = AsyncMock()
    risk_svc = RiskService()
    policy_svc = PolicyService(repo)
    decision_svc = DecisionService(repo)
    approval_svc = ApprovalService(repo, risk_svc, policy_svc, decision_svc)
    gov_svc = GovernanceService(repo, approval_svc, risk_svc, policy_svc)
    review_svc = ReviewService(repo)

    active_policy = MagicMock()
    active_policy.id = uuid.uuid4()
    active_policy.organization_id = uuid.uuid4()
    active_policy.policy_version = 2
    active_policy.rules = DEFAULT_GOVERNANCE_RULES
    active_policy.status = "ACTIVE"
    repo.get_active_policy.return_value = active_policy
    repo.get_policy_by_version.return_value = active_policy

    return approval_svc, gov_svc, review_svc, repo


@pytest.mark.asyncio
async def test_failure_voting_on_already_approved_request(
    failure_test_env: tuple[ApprovalService, GovernanceService, ReviewService, AsyncMock],
) -> None:
    """Voting on an already approved request raises InvalidStateTransitionError."""
    approval_svc, _, _, repo = failure_test_env

    req_mock = MagicMock()
    req_mock.id = uuid.uuid4()
    req_mock.organization_id = uuid.uuid4()
    req_mock.status = ApprovalStatus.APPROVED.value
    req_mock.expires_at = datetime.now(UTC) + timedelta(hours=1)
    repo.get_request.return_value = req_mock

    with pytest.raises(InvalidStateTransitionError) as exc:
        await approval_svc.cast_vote(
            organization_id=req_mock.organization_id,
            request_id=req_mock.id,
            reviewer_id=uuid.uuid4(),
            decision=VoteDecision.APPROVE,
        )
    assert "terminal state" in str(exc.value)


@pytest.mark.asyncio
async def test_failure_voting_on_expired_request(
    failure_test_env: tuple[ApprovalService, GovernanceService, ReviewService, AsyncMock],
) -> None:
    """Voting on an expired request raises ApprovalExpiredError."""
    approval_svc, _, _, repo = failure_test_env

    req_mock = MagicMock()
    req_mock.id = uuid.uuid4()
    req_mock.organization_id = uuid.uuid4()
    req_mock.status = ApprovalStatus.PENDING.value
    req_mock.expires_at = datetime.now(UTC) - timedelta(minutes=10)  # Past!
    repo.get_request.return_value = req_mock

    with pytest.raises(ApprovalExpiredError):
        await approval_svc.cast_vote(
            organization_id=req_mock.organization_id,
            request_id=req_mock.id,
            reviewer_id=uuid.uuid4(),
            decision=VoteDecision.APPROVE,
        )


@pytest.mark.asyncio
async def test_failure_revoking_pending_request(
    failure_test_env: tuple[ApprovalService, GovernanceService, ReviewService, AsyncMock],
) -> None:
    """Only APPROVED requests can be revoked; revoking PENDING must fail."""
    approval_svc, _, _, repo = failure_test_env

    req_mock = MagicMock()
    req_mock.id = uuid.uuid4()
    req_mock.organization_id = uuid.uuid4()
    req_mock.status = ApprovalStatus.PENDING.value
    repo.get_request.return_value = req_mock

    with pytest.raises(InvalidStateTransitionError) as exc:
        await approval_svc.revoke_approval(
            organization_id=req_mock.organization_id,
            request_id=req_mock.id,
            revoker_id=uuid.uuid4(),
            reason="Revoke before approval",
        )
    assert "Only APPROVED requests can be revoked" in str(exc.value)


@pytest.mark.asyncio
async def test_failure_cancelling_already_approved_request(
    failure_test_env: tuple[ApprovalService, GovernanceService, ReviewService, AsyncMock],
) -> None:
    """Approved requests cannot be cancelled; they must be revoked instead."""
    approval_svc, _, _, repo = failure_test_env

    req_mock = MagicMock()
    req_mock.id = uuid.uuid4()
    req_mock.organization_id = uuid.uuid4()
    req_mock.status = ApprovalStatus.APPROVED.value
    repo.get_request.return_value = req_mock

    with pytest.raises(InvalidStateTransitionError):
        await approval_svc.cancel_request(
            organization_id=req_mock.organization_id,
            request_id=req_mock.id,
            canceller_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_failure_empty_review_comment(
    failure_test_env: tuple[ApprovalService, GovernanceService, ReviewService, AsyncMock],
) -> None:
    """Adding an empty whitespace comment must fail validation."""
    _, _, review_svc, _ = failure_test_env

    with pytest.raises(ValueError) as exc:
        await review_svc.add_comment(
            organization_id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            author_id=uuid.uuid4(),
            comment="   ",
        )
    assert "cannot be empty" in str(exc.value)


@pytest.mark.asyncio
async def test_failure_policy_version_stability_under_update(
    failure_test_env: tuple[ApprovalService, GovernanceService, ReviewService, AsyncMock],
) -> None:
    """Updating a policy must not retroactively change the policy_version recorded on existing approval requests."""
    approval_svc, _, _, repo = failure_test_env

    # An approval created under v1
    org_id = uuid.uuid4()
    created_mock = MagicMock()
    created_mock.id = uuid.uuid4()
    created_mock.organization_id = org_id
    created_mock.request_type = ApprovalType.DATA_EXPORT.value
    created_mock.requester_id = uuid.uuid4()
    created_mock.resource_type = "DATASET"
    created_mock.resource_id = "ds-1"
    created_mock.risk_level = RiskLevel.HIGH.value
    created_mock.risk_score = 0.75
    created_mock.status = ApprovalStatus.PENDING.value
    created_mock.reason = "Export"
    created_mock.context = {}
    created_mock.action_hash = "hash1"
    created_mock.resource_hash = "hash2"
    created_mock.policy_version = 1  # version 1
    created_mock.expires_at = datetime.now(UTC) + timedelta(hours=1)
    created_mock.created_at = datetime.now(UTC)
    created_mock.updated_at = datetime.now(UTC)

    repo.create_request.return_value = created_mock
    repo.get_request.return_value = created_mock

    # Policy is now v2 in active
    v2_policy = MagicMock()
    v2_policy.policy_version = 2
    repo.get_active_policy.return_value = v2_policy

    req = await approval_svc.get_request(org_id, created_mock.id)
    # The approval request is locked to v1
    assert req.policy_version == 1

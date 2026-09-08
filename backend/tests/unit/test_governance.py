"""Unit tests for Governance domain, risk rules, state machine, and policy engine."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.governance.application.decision_service import (
    compute_action_hash,
    compute_decision_hash,
)
from app.governance.application.escalation_service import EscalationService
from app.governance.application.policy_service import DEFAULT_GOVERNANCE_RULES, PolicyService
from app.governance.application.risk_service import RiskService
from app.governance.domain.enums import (
    VALID_TRANSITIONS,
    ApprovalStatus,
    ApprovalType,
    RiskLevel,
)
from app.governance.domain.errors import PolicyViolationError
from app.governance.domain.models import (
    ApprovalQuorum,
    GovernancePolicy,
    RiskAssessment,
)


def test_deterministic_risk_external_side_effects() -> None:
    """Operations with external side effects must evaluate to CRITICAL."""
    service = RiskService()
    assessment = service.assess_risk(
        request_type=ApprovalType.QUERY_EXECUTION,
        factors={"external_side_effect": True, "operation_name": "send_email"},
    )
    assert assessment.risk_level == RiskLevel.CRITICAL
    assert assessment.risk_score >= 0.9
    assert any("external side effects" in r for r in assessment.reasons)


def test_deterministic_risk_agent_actions() -> None:
    """Agent high-risk operations must evaluate to HIGH or CRITICAL."""
    service = RiskService()
    # Tenant scoped agent action -> HIGH
    high_eval = service.assess_risk(
        request_type=ApprovalType.AGENT_HIGH_RISK_ACTION,
        factors={"scope": "ORGANIZATION"},
    )
    assert high_eval.risk_level == RiskLevel.HIGH
    assert high_eval.risk_score == 0.75

    # Destructive or global agent action -> CRITICAL
    crit_eval = service.assess_risk(
        request_type=ApprovalType.AGENT_HIGH_RISK_ACTION,
        factors={"destructive": True},
    )
    assert crit_eval.risk_level == RiskLevel.CRITICAL
    assert crit_eval.risk_score >= 0.95


def test_deterministic_risk_policy_and_model_changes() -> None:
    """Policy or Model mutations must evaluate to HIGH."""
    service = RiskService()
    p_eval = service.assess_risk(ApprovalType.POLICY_CHANGE)
    assert p_eval.risk_level == RiskLevel.HIGH

    m_eval = service.assess_risk(ApprovalType.MODEL_CHANGE)
    assert m_eval.risk_level == RiskLevel.HIGH


def test_deterministic_risk_data_export_thresholds() -> None:
    """Data export risks must scale deterministically with volume and sensitivity."""
    service = RiskService()

    # Small internal export -> LOW
    low_export = service.assess_risk(
        ApprovalType.DATA_EXPORT,
        factors={"row_count": 500, "data_sensitivity": "INTERNAL"},
    )
    assert low_export.risk_level == RiskLevel.LOW

    # Medium sensitive export -> HIGH
    high_export = service.assess_risk(
        ApprovalType.DATA_EXPORT,
        factors={"row_count": 5000, "data_sensitivity": "CONFIDENTIAL"},
    )
    assert high_export.risk_level == RiskLevel.HIGH

    # Massive sensitive export -> CRITICAL
    crit_export = service.assess_risk(
        ApprovalType.DATA_EXPORT,
        factors={"row_count": 60000, "data_sensitivity": "RESTRICTED"},
    )
    assert crit_export.risk_level == RiskLevel.CRITICAL


def test_deterministic_risk_publication() -> None:
    """Production semantic or graph publications must evaluate to HIGH."""
    service = RiskService()
    sem_eval = service.assess_risk(
        ApprovalType.SEMANTIC_PUBLICATION,
        factors={"is_production": True},
    )
    assert sem_eval.risk_level == RiskLevel.HIGH

    graph_eval = service.assess_risk(
        ApprovalType.GRAPH_PUBLICATION,
        factors={"critical_relationship": True},
    )
    assert graph_eval.risk_level == RiskLevel.HIGH


def test_policy_engine_tier_evaluation() -> None:
    """Policy engine maps risk tiers to correct approval requirements."""
    mock_repo = AsyncMock()
    policy_svc = PolicyService(mock_repo)

    policy = GovernancePolicy(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        policy_version=1,
        rules=DEFAULT_GOVERNANCE_RULES,
        status="ACTIVE",
    )

    # LOW risk -> no human approval needed
    low_req = policy_svc.evaluate_requirement(
        policy,
        RiskAssessment(risk_level=RiskLevel.LOW, risk_score=0.15),
        ApprovalType.QUERY_EXECUTION,
    )
    assert low_req.required is False
    assert low_req.minimum_approvers == 0

    # MEDIUM risk -> 1 approver (Analyst or Admin)
    med_req = policy_svc.evaluate_requirement(
        policy,
        RiskAssessment(risk_level=RiskLevel.MEDIUM, risk_score=0.45),
        ApprovalType.QUERY_EXECUTION,
    )
    assert med_req.required is True
    assert med_req.minimum_approvers == 1
    assert "Analyst" in med_req.required_roles

    # HIGH risk -> 1 Admin approver
    high_req = policy_svc.evaluate_requirement(
        policy,
        RiskAssessment(risk_level=RiskLevel.HIGH, risk_score=0.75),
        ApprovalType.DATA_EXPORT,
    )
    assert high_req.required is True
    assert high_req.minimum_approvers == 1
    assert high_req.required_roles == ["Admin"]

    # CRITICAL risk -> 2 Admin approvers
    crit_req = policy_svc.evaluate_requirement(
        policy,
        RiskAssessment(risk_level=RiskLevel.CRITICAL, risk_score=0.95),
        ApprovalType.AGENT_HIGH_RISK_ACTION,
    )
    assert crit_req.required is True
    assert crit_req.minimum_approvers >= 2
    assert crit_req.required_roles == ["Admin"]


@pytest.mark.asyncio
async def test_policy_engine_anti_downgrade_protection() -> None:
    """Attempts to disable human review for CRITICAL tier must be rejected."""
    mock_repo = AsyncMock()
    # Mock active policy
    active_mock = MagicMock()
    active_mock.id = uuid.uuid4()
    active_mock.organization_id = uuid.uuid4()
    active_mock.policy_version = 1
    active_mock.rules = DEFAULT_GOVERNANCE_RULES
    active_mock.status = "ACTIVE"
    active_mock.created_by = None
    active_mock.approved_by = None
    active_mock.created_at = None
    active_mock.updated_at = None
    mock_repo.get_active_policy.return_value = active_mock

    policy_svc = PolicyService(mock_repo)

    malicious_rules = {
        "risk_thresholds": {
            "CRITICAL": {
                "requires_human_approval": False,
                "minimum_approvers": 0,
            }
        }
    }

    with pytest.raises(PolicyViolationError) as exc:
        await policy_svc.update_policy(
            organization_id=active_mock.organization_id,
            new_rules=malicious_rules,
            creator_id=uuid.uuid4(),
        )
    assert "Anti-downgrade violation" in str(exc.value)


def test_quorum_calculation() -> None:
    """Quorum states must compute accurately."""
    # Single approver
    q1 = ApprovalQuorum(required=1, approved=0, rejected=0)
    assert q1.is_reached is False
    assert q1.is_rejected is False

    q1_approved = ApprovalQuorum(required=1, approved=1, rejected=0)
    assert q1_approved.is_reached is True

    # Multi-approver (Two-person rule)
    q2 = ApprovalQuorum(required=2, approved=1, rejected=0)
    assert q2.is_reached is False

    q2_reached = ApprovalQuorum(required=2, approved=2, rejected=0)
    assert q2_reached.is_reached is True

    # Rejection immediately prevents quorum
    q_rejected = ApprovalQuorum(required=2, approved=1, rejected=1)
    assert q_rejected.is_rejected is True


def test_cryptographic_hashes_integrity() -> None:
    """Action and Decision hashes must be deterministic and tamper-evident."""
    payload_a = {"query": "SELECT * FROM users", "limit": 100}
    payload_b = {"limit": 100, "query": "SELECT * FROM users"}  # different key order
    payload_c = {"query": "SELECT * FROM users WHERE admin = 1"}

    hash_a = compute_action_hash(payload_a)
    hash_b = compute_action_hash(payload_b)
    hash_c = compute_action_hash(payload_c)

    # Identical content with different ordering produces identical hash
    assert hash_a == hash_b
    # Mutated payload produces completely different hash
    assert hash_a != hash_c

    # Decision hash
    req_id = uuid.uuid4()
    d_hash = compute_decision_hash(
        request_id=req_id,
        decision="APPROVED",
        reviewer_ids=["u1", "u2"],
        policy_version=1,
        risk_score=0.75,
    )
    assert len(d_hash) == 64


def test_legal_state_machine_transitions() -> None:
    """Verify strictly defined valid state transitions."""
    assert ApprovalStatus.IN_REVIEW in VALID_TRANSITIONS[ApprovalStatus.PENDING]
    assert ApprovalStatus.APPROVED in VALID_TRANSITIONS[ApprovalStatus.IN_REVIEW]
    assert ApprovalStatus.CHANGES_REQUESTED in VALID_TRANSITIONS[ApprovalStatus.IN_REVIEW]
    assert ApprovalStatus.REVOKED in VALID_TRANSITIONS[ApprovalStatus.APPROVED]

    # Terminal states have no outbound transitions
    assert len(VALID_TRANSITIONS[ApprovalStatus.REJECTED]) == 0
    assert len(VALID_TRANSITIONS[ApprovalStatus.EXPIRED]) == 0
    assert len(VALID_TRANSITIONS[ApprovalStatus.CANCELLED]) == 0
    assert len(VALID_TRANSITIONS[ApprovalStatus.REVOKED]) == 0


@pytest.mark.asyncio
async def test_escalation_service_expiration() -> None:
    """Escalation service expires timed-out requests."""
    mock_repo = AsyncMock()
    req_mock = MagicMock()
    req_mock.id = uuid.uuid4()
    req_mock.organization_id = uuid.uuid4()
    req_mock.request_type = ApprovalType.QUERY_EXECUTION.value
    req_mock.requester_id = uuid.uuid4()
    req_mock.resource_type = "QUERY"
    req_mock.resource_id = "q-123"
    req_mock.risk_level = RiskLevel.HIGH.value
    req_mock.risk_score = 0.75
    req_mock.status = ApprovalStatus.PENDING.value
    req_mock.reason = "Need query approval"
    req_mock.context = {}
    req_mock.action_hash = "h1"
    req_mock.resource_hash = "h2"
    req_mock.policy_version = 1
    req_mock.expires_at = datetime.now(UTC) - timedelta(hours=2)
    req_mock.created_at = datetime.now(UTC) - timedelta(hours=3)
    req_mock.updated_at = datetime.now(UTC) - timedelta(hours=3)

    mock_repo.get_expired_pending_requests.return_value = [req_mock]

    escalation_svc = EscalationService(mock_repo)
    expired_list = await escalation_svc.process_expired_requests()

    assert len(expired_list) == 1
    assert req_mock.status == ApprovalStatus.EXPIRED.value
    assert expired_list[0].status == ApprovalStatus.EXPIRED

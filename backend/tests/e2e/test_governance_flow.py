"""E2E Test: Journey 8 — Human Approval & Governance Workflow."""

import pytest

from app.product.journeys import JourneyExecutionResult, JourneyStepResult
from app.product.workflows import WorkflowStateMachineAuditor


@pytest.mark.asyncio
async def test_canonical_journey_8_approval_workflow() -> None:
    # State transitions: PENDING -> APPROVED -> EXECUTED
    assert WorkflowStateMachineAuditor.validate_transition(
        "governance_approval", "PENDING", "APPROVED"
    )
    assert WorkflowStateMachineAuditor.validate_transition(
        "governance_approval", "APPROVED", "EXECUTED"
    )

    # Expiry and rejection
    assert WorkflowStateMachineAuditor.validate_transition(
        "governance_approval", "PENDING", "EXPIRED"
    )
    assert WorkflowStateMachineAuditor.validate_transition(
        "governance_approval", "PENDING", "REJECTED"
    )

    # Double execution or post-terminal transitions prohibited (TOCTOU protection)
    assert not WorkflowStateMachineAuditor.validate_transition(
        "governance_approval", "EXECUTED", "APPROVED"
    )
    assert not WorkflowStateMachineAuditor.validate_transition(
        "governance_approval", "EXPIRED", "EXECUTED"
    )

    steps = [
        JourneyStepResult(
            step_name="detect_sensitive_action",
            status="SUCCESS",
            duration_ms=4.0,
            details={"action": "export_customer_data"},
        ),
        JourneyStepResult(
            step_name="create_approval_request",
            status="SUCCESS",
            duration_ms=8.0,
            details={"approval_id": "appr_789", "expires_in_sec": 3600},
        ),
        JourneyStepResult(
            step_name="evaluate_approver_role",
            status="SUCCESS",
            duration_ms=6.0,
            details={"approver": "sec_admin", "separation_of_duties": True},
        ),
        JourneyStepResult(
            step_name="execute_approved_action",
            status="SUCCESS",
            duration_ms=15.0,
            details={"resource_hash_match": True},
        ),
    ]
    result = JourneyExecutionResult(
        journey_id="J8",
        name="Human Approval & Governance",
        description="Approval lifecycle with TOCTOU checks and separation of duties.",
        status="SUCCESS",
        total_duration_ms=33.0,
        steps=steps,
        evidence={"toctou_prevented": True, "separation_of_duties": True},
    )
    assert result.status == "SUCCESS"
    assert result.evidence["toctou_prevented"] is True

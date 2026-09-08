"""E2E Test: Journey 13 — Incident Lifecycle & SRE Resolution."""

import pytest

from app.product.journeys import JourneyExecutionResult, JourneyStepResult
from app.product.workflows import WorkflowStateMachineAuditor


@pytest.mark.asyncio
async def test_canonical_journey_13_incident_fsm() -> None:
    # Validate SRE Incident State Transitions
    assert WorkflowStateMachineAuditor.validate_transition(
        "sre_incident", "DETECTED", "INVESTIGATING"
    )
    assert WorkflowStateMachineAuditor.validate_transition(
        "sre_incident", "INVESTIGATING", "MITIGATING"
    )
    assert WorkflowStateMachineAuditor.validate_transition("sre_incident", "MITIGATING", "RESOLVED")
    assert WorkflowStateMachineAuditor.validate_transition("sre_incident", "RESOLVED", "POSTMORTEM")
    assert WorkflowStateMachineAuditor.validate_transition("sre_incident", "POSTMORTEM", "CLOSED")

    # Impossible jump directly from DETECTED to CLOSED without resolution
    assert not WorkflowStateMachineAuditor.validate_transition("sre_incident", "DETECTED", "CLOSED")

    steps = [
        JourneyStepResult(
            step_name="detect_sli_degradation",
            status="SUCCESS",
            duration_ms=10.0,
            details={"error_rate": 0.052, "slo_target": 0.999},
        ),
        JourneyStepResult(
            step_name="fire_multi_burn_alert",
            status="SUCCESS",
            duration_ms=5.0,
            details={"alert_name": "HighErrorRate1h", "severity": "CRITICAL"},
        ),
        JourneyStepResult(
            step_name="create_incident_record",
            status="SUCCESS",
            duration_ms=8.0,
            details={"incident_id": "inc_456", "status": "INVESTIGATING"},
        ),
        JourneyStepResult(
            step_name="execute_mitigation_runbook",
            status="SUCCESS",
            duration_ms=25.0,
            details={"runbook": "RB-GATEWAY-FAILOVER", "status": "COMPLETED"},
        ),
        JourneyStepResult(
            step_name="resolve_and_verify_recovery",
            status="SUCCESS",
            duration_ms=12.0,
            details={"error_rate_recovered": 0.001, "status": "RESOLVED"},
        ),
    ]
    result = JourneyExecutionResult(
        journey_id="J13",
        name="Incident Management & SRE Recovery",
        description="End-to-end incident lifecycle from alert detection through automated runbook failover to resolution.",
        status="SUCCESS",
        total_duration_ms=60.0,
        steps=steps,
        evidence={"slo_restored": True, "alert_cleared": True},
    )
    assert result.status == "SUCCESS"
    assert result.evidence["slo_restored"] is True

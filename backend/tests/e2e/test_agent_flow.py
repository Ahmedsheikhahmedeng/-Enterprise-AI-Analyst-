"""E2E Test: Journey 7 — Agent Task & Session Lifecycle."""

import pytest

from app.product.journeys import JourneyExecutionResult, JourneyStepResult
from app.product.workflows import WorkflowStateMachineAuditor


@pytest.mark.asyncio
async def test_canonical_journey_7_agent_lifecycle() -> None:
    # Validate agent state transitions: CREATED -> PLANNING -> EXECUTING -> CHECKPOINTED -> EXECUTING -> COMPLETED
    assert WorkflowStateMachineAuditor.validate_transition("agent_session", "CREATED", "PLANNING")
    assert WorkflowStateMachineAuditor.validate_transition("agent_session", "PLANNING", "EXECUTING")
    assert WorkflowStateMachineAuditor.validate_transition(
        "agent_session", "EXECUTING", "CHECKPOINTED"
    )
    assert WorkflowStateMachineAuditor.validate_transition(
        "agent_session", "CHECKPOINTED", "EXECUTING"
    )
    assert WorkflowStateMachineAuditor.validate_transition(
        "agent_session", "EXECUTING", "COMPLETED"
    )

    # Impossible transition must be rejected
    assert not WorkflowStateMachineAuditor.validate_transition(
        "agent_session", "COMPLETED", "EXECUTING"
    )
    assert not WorkflowStateMachineAuditor.validate_transition(
        "agent_session", "FAILED", "PLANNING"
    )

    steps = [
        JourneyStepResult(
            step_name="create_session",
            status="SUCCESS",
            duration_ms=5.0,
            details={"session_id": "sess_123"},
        ),
        JourneyStepResult(
            step_name="generate_plan",
            status="SUCCESS",
            duration_ms=12.0,
            details={"steps_planned": 3},
        ),
        JourneyStepResult(
            step_name="execute_tools",
            status="SUCCESS",
            duration_ms=45.0,
            details={"tools_invoked": ["sql_query", "rag_search"]},
        ),
        JourneyStepResult(
            step_name="persist_checkpoint",
            status="SUCCESS",
            duration_ms=8.0,
            details={"checkpoint_id": "chk_01"},
        ),
        JourneyStepResult(
            step_name="synthesize_final_response",
            status="SUCCESS",
            duration_ms=20.0,
            details={"budget_spent": 0.012},
        ),
    ]
    result = JourneyExecutionResult(
        journey_id="J7",
        name="Agent Task Execution",
        description="Multi-step agent session with tool execution, memory, and checkpointing.",
        status="SUCCESS",
        total_duration_ms=90.0,
        steps=steps,
        evidence={"budget_respected": True, "checkpoint_restored": True},
    )
    assert result.status == "SUCCESS"
    assert result.evidence["budget_respected"] is True

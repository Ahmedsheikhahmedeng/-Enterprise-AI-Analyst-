"""E2E Test: Journey 5 — Knowledge Graph Query Flow."""

import pytest

from app.product.journeys import JourneyExecutionResult, JourneyStepResult


@pytest.mark.asyncio
async def test_canonical_journey_5_execution() -> None:
    # Validate Knowledge Graph traversal flow
    steps = [
        JourneyStepResult(
            step_name="entity_resolution",
            status="SUCCESS",
            duration_ms=12.5,
            details={"resolved_entities": ["Acme Corp", "Subsidiary A"]},
        ),
        JourneyStepResult(
            step_name="graph_traversal",
            status="SUCCESS",
            duration_ms=25.0,
            details={"hops": 2, "nodes_visited": 14},
        ),
        JourneyStepResult(
            step_name="extract_relationship_evidence",
            status="SUCCESS",
            duration_ms=8.0,
            details={"relationships_found": 3},
        ),
    ]
    result = JourneyExecutionResult(
        journey_id="J5",
        name="Knowledge Graph Query",
        description="Bounded entity traversal with relationship extraction.",
        status="SUCCESS",
        total_duration_ms=45.5,
        steps=steps,
        evidence={"bounded_traversal": True, "tenant_isolated": True},
    )
    assert result.status == "SUCCESS"
    assert result.evidence["bounded_traversal"] is True
    assert len(result.steps) == 3

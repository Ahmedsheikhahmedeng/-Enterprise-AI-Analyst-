"""E2E Test: Journey 12 — FinOps & Cost Governance Flow."""

import pytest

from app.product.journeys import CanonicalJourneysRunner


@pytest.mark.asyncio
async def test_canonical_journey_12_finops_lifecycle() -> None:
    result = await CanonicalJourneysRunner.run_journey_12_finops(tokens=1500, model="gpt-4o")
    assert result.status == "SUCCESS"
    assert result.journey_id == "J12"
    assert len(result.steps) == 5
    assert result.evidence["non_negative_cost"] is True
    assert result.evidence["attributed"] is True

    step_map = {s.step_name: s for s in result.steps}
    assert step_map["lookup_pricing"].status == "SUCCESS"
    assert step_map["record_cost_event"].details["cost"] > 0
    assert step_map["check_budget_burn"].details["budget_status"] == "HEALTHY"
    assert step_map["evaluate_quota"].details["remaining_quota"] > 0

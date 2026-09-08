"""E2E Test: Journey 4 — Structured Analytics (Secure SQL) Flow."""

import pytest

from app.product.journeys import CanonicalJourneysRunner


@pytest.mark.asyncio
async def test_canonical_journey_4_execution() -> None:
    result = await CanonicalJourneysRunner.run_journey_4_structured_analytics(
        natural_query="Find top 5 sales regions by quarterly growth"
    )
    assert result.status == "SUCCESS"
    assert result.journey_id == "J4"
    assert len(result.steps) == 5
    assert result.evidence["read_only_enforced"] is True
    assert result.evidence["row_limit_applied"] is True

    step_map = {s.step_name: s for s in result.steps}
    assert step_map["validate_sql_security"].details["read_only"] is True
    assert step_map["execute_bounded_sql"].details["row_limit"] == 1000

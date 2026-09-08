"""E2E Test: Journey 6 — Hybrid Analyst Flow (RAG + SQL + Graph)."""

import pytest

from app.product.journeys import CanonicalJourneysRunner


@pytest.mark.asyncio
async def test_canonical_journey_6_execution() -> None:
    result = await CanonicalJourneysRunner.run_journey_6_hybrid_analyst(
        query="Reconcile revenue figures from SQL with corporate filings"
    )
    assert result.status == "SUCCESS"
    assert result.journey_id == "J6"
    assert len(result.steps) == 4
    assert result.evidence["multi_modal_merged"] is True
    assert result.evidence["confidence"] >= 0.90

    step_map = {s.step_name: s for s in result.steps}
    assert "RAG" in step_map["parallel_dispatch"].details["modes"]
    assert "SQL" in step_map["parallel_dispatch"].details["modes"]
    assert "GRAPH" in step_map["parallel_dispatch"].details["modes"]
    assert step_map["conflict_detection"].details["conflicts_found"] == 0

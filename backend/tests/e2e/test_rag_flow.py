"""E2E Test: Journey 3 — Knowledge Query (RAG) Flow."""

import pytest

from app.product.journeys import CanonicalJourneysRunner


@pytest.mark.asyncio
async def test_canonical_journey_3_execution() -> None:
    result = await CanonicalJourneysRunner.run_journey_3_knowledge_query(
        query="Explain our Q3 corporate expansion plans"
    )
    assert result.status == "SUCCESS"
    assert result.journey_id == "J3"
    assert len(result.steps) == 4
    assert result.evidence["grounded"] is True
    assert result.evidence["citations_present"] is True

    step_map = {s.step_name: s for s in result.steps}
    assert step_map["query_understanding"].status == "SUCCESS"
    assert step_map["hybrid_retrieval"].status == "SUCCESS"
    assert step_map["rerank"].status == "SUCCESS"
    assert step_map["evidence_synthesis"].status == "SUCCESS"

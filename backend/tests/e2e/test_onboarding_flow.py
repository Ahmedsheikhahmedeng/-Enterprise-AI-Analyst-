"""E2E Test: Journey 2 — Data Onboarding Flow."""

import pytest

from app.product.journeys import CanonicalJourneysRunner


@pytest.mark.asyncio
async def test_canonical_journey_2_execution() -> None:
    result = await CanonicalJourneysRunner.run_journey_2_data_onboarding(
        dataset_name="Quarterly Financials", file_count=3
    )
    assert result.status == "SUCCESS"
    assert result.journey_id == "J2"
    assert len(result.steps) == 6
    assert result.evidence["lineage_preserved"] is True
    assert result.evidence["embedding_state"] == "INDEXED"

    step_names = [s.step_name for s in result.steps]
    assert "upload_dataset" in step_names
    assert "chunk_content" in step_names
    assert "generate_embeddings" in step_names
    assert "classify_data" in step_names

"""E2E Test: Journey 14 — SRE, Security, and FinOps Release Safety Gates."""

import pytest

from app.product.journeys import CanonicalJourneysRunner


@pytest.mark.asyncio
async def test_canonical_journey_14_release_gate_allow() -> None:
    # All checks healthy -> ALLOW
    result = await CanonicalJourneysRunner.run_journey_14_release_safety(simulate_blocker=False)
    assert result.status == "SUCCESS"
    assert result.journey_id == "J14"
    assert result.evidence["decision"] == "ALLOW"
    assert all(s.status == "SUCCESS" for s in result.steps)


@pytest.mark.asyncio
async def test_canonical_journey_14_release_gate_block() -> None:
    # Simulated budget exhaustion or SLO breach -> BLOCK
    result = await CanonicalJourneysRunner.run_journey_14_release_safety(simulate_blocker=True)
    assert result.status == "FAILED"
    assert result.evidence["decision"] == "BLOCK"
    failed_steps = [s for s in result.steps if s.status == "FAILED"]
    assert len(failed_steps) >= 1

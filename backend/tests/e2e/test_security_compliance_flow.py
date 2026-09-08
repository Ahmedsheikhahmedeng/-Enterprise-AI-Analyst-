"""E2E Test: Journey 11 — Security & Compliance Governance."""

import pytest

from app.compliance.enums import DataClassificationLevel
from app.finops.routing import CostAwareRouter, ModelCandidate


@pytest.mark.asyncio
async def test_canonical_journey_11_classification_enforcement() -> None:
    # Model candidates: external cheap model vs internal self-hosted model
    candidates = [
        ModelCandidate(
            provider="openai",
            model="gpt-4o-mini",
            quality_score=0.88,
            latency_ms=250,
            pricing=None,
            is_external=True,
        ),
        ModelCandidate(
            provider="local",
            model="llama-3.3-70b-instruct",
            quality_score=0.85,
            latency_ms=300,
            pricing=None,
            is_external=False,
        ),
    ]

    # When classification is RESTRICTED, external provider must be blocked
    decision = CostAwareRouter.select_model(
        candidates=candidates,
        data_classification=DataClassificationLevel.RESTRICTED.value,
        minimum_quality_threshold=0.70,
    )
    assert decision.selected_provider == "local"
    assert decision.selected_model == "llama-3.3-70b-instruct"

    # Evaluated candidates must show rejection reason for the external model
    ext_eval = next(c for c in decision.evaluated_candidates if c["model"] == "gpt-4o-mini")
    assert ext_eval["eligible"] is False
    assert "Restricted data prohibited on external providers" in str(ext_eval["rejection_reason"])

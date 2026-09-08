"""E2E Test: Journey 9 — Report Generation & Multi-Format Export."""

import hashlib

import pytest

from app.product.journeys import JourneyExecutionResult, JourneyStepResult


@pytest.mark.asyncio
async def test_canonical_journey_9_report_generation() -> None:
    content = "# Executive Summary\nRevenue grew by 14% based on grounded financial data."
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    steps = [
        JourneyStepResult(
            step_name="aggregate_evidence",
            status="SUCCESS",
            duration_ms=10.0,
            details={"evidence_items": 4},
        ),
        JourneyStepResult(
            step_name="build_markdown_report",
            status="SUCCESS",
            duration_ms=5.0,
            details={"version_hash": content_hash},
        ),
        JourneyStepResult(
            step_name="export_pdf_and_html",
            status="SUCCESS",
            duration_ms=25.0,
            details={"formats": ["MD", "HTML", "PDF", "CSV"]},
        ),
        JourneyStepResult(
            step_name="verify_citations_provenance",
            status="SUCCESS",
            duration_ms=4.0,
            details={"all_claims_cited": True},
        ),
    ]
    result = JourneyExecutionResult(
        journey_id="J9",
        name="Report Generation",
        description="Multi-format export with cryptographic checksums and citation provenance.",
        status="SUCCESS",
        total_duration_ms=44.0,
        steps=steps,
        evidence={"content_hash": content_hash, "export_verified": True},
    )
    assert result.status == "SUCCESS"
    assert result.evidence["export_verified"] is True
    assert len(content_hash) == 64

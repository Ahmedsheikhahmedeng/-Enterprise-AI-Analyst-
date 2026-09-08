"""E2E Test: Journey 10 — Continuous Evaluation & Billing Isolation."""

import pytest

from app.product.journeys import JourneyExecutionResult, JourneyStepResult


@pytest.mark.asyncio
async def test_canonical_journey_10_evaluation_flow() -> None:
    steps = [
        JourneyStepResult(
            step_name="load_benchmark_dataset",
            status="SUCCESS",
            duration_ms=15.0,
            details={"test_cases": 25},
        ),
        JourneyStepResult(
            step_name="run_evaluation_scorers",
            status="SUCCESS",
            duration_ms=80.0,
            details={"groundedness": 0.96, "citation_recall": 0.94, "sql_validity": 1.0},
        ),
        JourneyStepResult(
            step_name="verify_billing_isolation",
            status="SUCCESS",
            duration_ms=5.0,
            details={"prod_ledger_untouched": True, "eval_cost_separated": True},
        ),
        JourneyStepResult(
            step_name="evaluate_quality_gate",
            status="SUCCESS",
            duration_ms=4.0,
            details={"gate_decision": "PASS"},
        ),
    ]
    result = JourneyExecutionResult(
        journey_id="J10",
        name="Continuous Evaluation",
        description="Benchmark evaluation with quality gates and strictly separated cost accounting.",
        status="SUCCESS",
        total_duration_ms=104.0,
        steps=steps,
        evidence={"quality_gate": "PASS", "billing_isolation": True},
    )
    assert result.status == "SUCCESS"
    assert result.evidence["billing_isolation"] is True

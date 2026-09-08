"""Integration tests verifying end-to-end continuous evaluation, regressions, quality gates, and release decisions."""

import uuid

import pytest

from app.continuous_evaluation.application.benchmark_service import BenchmarkService
from app.continuous_evaluation.application.calibration_service import CalibrationService
from app.continuous_evaluation.application.comparison_service import ComparisonService
from app.continuous_evaluation.application.evaluation_service import ContinuousEvaluationService
from app.continuous_evaluation.application.quality_gate_service import QualityGateService
from app.continuous_evaluation.application.regression_service import RegressionService
from app.continuous_evaluation.application.release_service import ReleaseQualityPolicy
from app.continuous_evaluation.domain.enums import (
    EvaluationTarget,
    QualityGateDecision,
    RegressionSeverity,
    ReleaseStatus,
)
from app.continuous_evaluation.domain.errors import ReleaseBlockedError
from app.continuous_evaluation.domain.models import QualityGateRule
from app.models.evaluation import EvaluationCase, EvaluationCaseResult
from tests.unit.test_continuous_evaluation import MockContinuousEvaluationRepository


@pytest.mark.asyncio
async def test_full_continuous_evaluation_pipeline() -> None:
    """Tests complete flow: Benchmark -> Slices -> Scorecard -> Baseline -> Candidate -> Regression -> Gate -> Release."""
    repo = MockContinuousEvaluationRepository()
    benchmark_svc = BenchmarkService(repo)
    eval_svc = ContinuousEvaluationService(repo)
    regression_svc = RegressionService(repo)
    gate_svc = QualityGateService(repo)
    calibration_svc = CalibrationService(repo)
    comparison_svc = ComparisonService(repo)
    release_policy = ReleaseQualityPolicy()

    org_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    # 1. Create versioned benchmark
    benchmark = await benchmark_svc.create_benchmark(
        organization_id=org_id,
        name="Enterprise End-to-End Benchmark",
        task_type="END_TO_END",
        target=EvaluationTarget.END_TO_END,
        dataset_id=dataset_id,
        version=1,
    )
    assert benchmark.version == 1

    # 2. Simulate baseline run case results
    baseline_run_id = uuid.uuid4()
    case_1_id = uuid.uuid4()
    case_2_id = uuid.uuid4()

    case_1 = EvaluationCase(
        id=case_1_id,
        organization_id=org_id,
        dataset_id=dataset_id,
        query="RAG query",
        difficulty="EASY",
        language="en",
        route_expected="RAG",
    )
    case_2 = EvaluationCase(
        id=case_2_id,
        organization_id=org_id,
        dataset_id=dataset_id,
        query="SQL query",
        difficulty="HARD",
        language="ar",
        route_expected="SQL",
    )

    baseline_case_results = [
        EvaluationCaseResult(
            id=uuid.uuid4(),
            organization_id=org_id,
            run_id=baseline_run_id,
            case_id=case_1_id,
            actual_route="RAG",
            expected_route="RAG",
            grounding_score=0.95,
            citation_score=0.92,
            sql_score=0.0,
            retrieval_score=0.90,
            passed=True,
            metrics_detail={"evidence": ["chunk_1", "chunk_2"]},
        ),
        EvaluationCaseResult(
            id=uuid.uuid4(),
            organization_id=org_id,
            run_id=baseline_run_id,
            case_id=case_2_id,
            actual_route="SQL",
            expected_route="SQL",
            grounding_score=1.0,
            citation_score=1.0,
            sql_score=1.0,
            retrieval_score=1.0,
            passed=True,
            metrics_detail={"evidence": ["table_1"]},
        ),
    ]
    baseline_case_results[0].case = case_1
    baseline_case_results[1].case = case_2

    # Test slice computation
    slices = eval_svc.compute_slices(baseline_case_results)
    assert slices["by_difficulty"]["EASY"] == 1.0
    assert slices["by_difficulty"]["HARD"] == 1.0
    assert slices["by_language"]["en"] == 1.0
    assert slices["by_language"]["ar"] == 1.0

    # Test route quality
    route_quality = eval_svc.compute_route_quality(baseline_case_results)
    assert route_quality["route_accuracy"] == 1.0
    assert route_quality["rag_route_accuracy"] == 1.0
    assert route_quality["sql_route_accuracy"] == 1.0

    # 3. Associate baseline with benchmark
    await benchmark_svc.set_baseline_run(benchmark.id, baseline_run_id, org_id)

    # 4. Simulate candidate run with regression
    candidate_run_id = uuid.uuid4()
    candidate_case_results = [
        EvaluationCaseResult(
            id=uuid.uuid4(),
            organization_id=org_id,
            run_id=candidate_run_id,
            case_id=baseline_case_results[0].case_id,
            actual_route="SQL",  # Wrong route!
            expected_route="RAG",
            grounding_score=0.60,  # Dropped from 0.95!
            citation_score=0.70,
            sql_score=0.0,
            retrieval_score=0.50,
            passed=False,
            failure_reason="Wrong route and ungrounded response",
            metrics_detail={"evidence": []},
        ),
        EvaluationCaseResult(
            id=uuid.uuid4(),
            organization_id=org_id,
            run_id=candidate_run_id,
            case_id=baseline_case_results[1].case_id,
            actual_route="SQL",
            expected_route="SQL",
            grounding_score=0.98,
            citation_score=0.95,
            sql_score=0.95,
            retrieval_score=1.0,
            passed=True,
            metrics_detail={"evidence": ["table_1"]},
        ),
    ]
    candidate_case_results[0].case = baseline_case_results[0].case
    candidate_case_results[1].case = baseline_case_results[1].case

    candidate_baseline_metrics = {
        "groundedness": 0.95,
        "citation_precision": 0.92,
        "route_accuracy": 1.0,
    }
    candidate_metrics = {"groundedness": 0.70, "citation_precision": 0.85, "route_accuracy": 0.50}

    # 5. Detect regression
    findings = await regression_svc.detect_regressions(
        benchmark_id=benchmark.id,
        run_id=candidate_run_id,
        baseline_run_id=baseline_run_id,
        organization_id=org_id,
        baseline_metrics=candidate_baseline_metrics,
        candidate_metrics=candidate_metrics,
        baseline_results=baseline_case_results,
        candidate_results=candidate_case_results,
    )

    assert len(findings) >= 1
    # Check groundedness regression finding
    grounding_reg = next(f for f in findings if f.metric_name == "groundedness")
    assert grounding_reg.severity == RegressionSeverity.CRITICAL

    # 6. Evaluate Quality Gate
    gate_rules = [
        QualityGateRule(metric_name="groundedness", min_threshold=0.90, is_critical=True),
        QualityGateRule(metric_name="route_accuracy", min_threshold=0.95, is_critical=True),
    ]
    gate_id = await gate_svc.create_gate(org_id, "Enterprise Production Gate", gate_rules)

    scorecard = {
        "metrics": candidate_metrics,
        "segmented_scores": {"quality_score": 0.65},
    }
    gate_result = await gate_svc.evaluate_gate(
        gate_id=gate_id,
        run_id=candidate_run_id,
        scorecard=scorecard,
        organization_id=org_id,
        regressions=findings,
    )

    # Must BLOCK_RELEASE due to critical threshold breach
    assert gate_result.decision == QualityGateDecision.BLOCK_RELEASE
    assert len(gate_result.violations) >= 1

    # 7. Release Quality Policy Decision
    status, reason = release_policy.evaluate_release_decision(
        [gate_result], approver_is_agent=False
    )
    assert status == ReleaseStatus.REJECTED
    assert "BLOCK_RELEASE" in reason

    with pytest.raises(ReleaseBlockedError, match="BLOCK_RELEASE"):
        release_policy.enforce_release([gate_result], approver_is_agent=False)

    # 8. Confidence Calibration
    predictions = [(0.92, False), (0.95, True), (0.80, True), (0.75, False)]
    calibration = calibration_svc.compute_calibration(candidate_run_id, predictions, num_buckets=5)
    assert calibration.ece >= 0.0
    assert calibration.brier_score >= 0.0

    # 9. Comparison Report
    comp_report = comparison_svc.compare_scorecards(
        comparison_type="MODEL",
        baseline_id=str(baseline_run_id),
        candidate_id=str(candidate_run_id),
        baseline_scorecard={
            "metrics": candidate_baseline_metrics,
            "segmented_scores": {"quality_score": 0.95},
        },
        candidate_scorecard=scorecard,
    )
    assert comp_report.winner == str(baseline_run_id)

"""Failure injection tests for Enterprise Continuous AI Evaluation."""

import uuid

import pytest

from app.continuous_evaluation.application.benchmark_service import BenchmarkService
from app.continuous_evaluation.application.metric_registry import MetricRegistry
from app.continuous_evaluation.application.monitoring_service import MonitoringService
from app.continuous_evaluation.application.quality_gate_service import QualityGateService
from app.continuous_evaluation.application.regression_service import (
    SignificanceAnalyzer,
)
from app.continuous_evaluation.domain.errors import BenchmarkNotFoundError, QualityGateNotFoundError
from app.continuous_evaluation.domain.models import HumanEvaluation
from tests.unit.test_continuous_evaluation import MockContinuousEvaluationRepository


def test_invalid_category_weights_failure() -> None:
    """Ensure registry rejects invalid or non-positive weight totals."""
    registry = MetricRegistry()
    with pytest.raises(ValueError, match="Total weights must be strictly positive"):
        registry.update_category_weights({"grounding": 0.0, "retrieval": 0.0})


@pytest.mark.asyncio
async def test_missing_benchmark_failure() -> None:
    """Ensure accessing nonexistent benchmark triggers BenchmarkNotFoundError."""
    repo = MockContinuousEvaluationRepository()
    service = BenchmarkService(repo)
    with pytest.raises(BenchmarkNotFoundError):
        await service.get_benchmark(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_missing_quality_gate_failure() -> None:
    """Ensure evaluating nonexistent gate triggers QualityGateNotFoundError."""
    repo = MockContinuousEvaluationRepository()
    service = QualityGateService(repo)
    with pytest.raises(QualityGateNotFoundError):
        await service.evaluate_gate(uuid.uuid4(), uuid.uuid4(), {}, uuid.uuid4())


def test_insufficient_sample_size_handling() -> None:
    """Ensure analyzer returns INSUFFICIENT_SAMPLE without declaring premature regression."""
    analyzer = SignificanceAnalyzer(min_samples=15)
    baseline = [0.95, 0.94, 0.96]
    candidate = [0.80, 0.82, 0.81]
    is_sig, p_val, note = analyzer.analyze_paired_difference(baseline, candidate)
    assert not is_sig
    assert p_val is None
    assert note == "INSUFFICIENT_SAMPLE"


@pytest.mark.asyncio
async def test_human_evaluation_out_of_bounds_score_failure() -> None:
    """Ensure human evaluation rejects ratings outside 1.0 - 5.0 range."""
    repo = MockContinuousEvaluationRepository()
    service = MonitoringService(repo)

    # Score below 1.0
    with pytest.raises(ValueError, match="accuracy_score must be strictly between 1.0 and 5.0"):
        await service.record_human_review(
            organization_id=uuid.uuid4(),
            evaluator_id=uuid.uuid4(),
            accuracy_score=0.5,
            helpfulness_score=4.0,
            grounding_score=4.0,
            clarity_score=4.0,
        )

    # Score above 5.0
    with pytest.raises(ValueError, match="grounding_score must be strictly between 1.0 and 5.0"):
        await service.record_human_review(
            organization_id=uuid.uuid4(),
            evaluator_id=uuid.uuid4(),
            accuracy_score=4.0,
            helpfulness_score=4.0,
            grounding_score=5.5,
            clarity_score=4.0,
        )


def test_llm_judge_drift_and_disagreement_detection() -> None:
    """Test detection of significant drift between human ground truth and LLM judge."""
    service = MonitoringService(MockContinuousEvaluationRepository())
    org_id = uuid.uuid4()
    eval_id = uuid.uuid4()

    # Create human evaluations: all 5.0 -> normalized score = 1.0
    human_evals = [
        HumanEvaluation(
            id=uuid.uuid4(),
            organization_id=org_id,
            evaluator_id=eval_id,
            accuracy_score=5.0,
            helpfulness_score=5.0,
            grounding_score=5.0,
            clarity_score=5.0,
        )
        for _ in range(5)
    ]

    # LLM Judge gave very low scores (0.2) -> divergence > 0.25 threshold
    judge_scores = [0.2, 0.2, 0.2, 0.2, 0.2]
    report = service.analyze_judge_bias(human_evals, judge_scores)
    assert report.total_samples == 5
    assert report.disagreement_count == 5
    assert report.agreement_rate == 0.0
    assert report.drift_score > 0.70

"""Unit tests for Enterprise Continuous AI Evaluation, Benchmarking & Quality Monitoring."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.continuous_evaluation.application.benchmark_service import BenchmarkService
from app.continuous_evaluation.application.calibration_service import CalibrationService
from app.continuous_evaluation.application.comparison_service import ComparisonService
from app.continuous_evaluation.application.metric_registry import MetricRegistry
from app.continuous_evaluation.application.monitoring_service import (
    MonitoringService,
    PrivacySanitizer,
)
from app.continuous_evaluation.application.quality_gate_service import QualityGateService
from app.continuous_evaluation.application.regression_service import (
    RegressionService,
    SignificanceAnalyzer,
)
from app.continuous_evaluation.application.release_service import ReleaseQualityPolicy
from app.continuous_evaluation.domain.enums import (
    EvaluationTarget,
    QualityGateDecision,
    RegressionSeverity,
    ReleaseStatus,
    SamplingStrategy,
)
from app.continuous_evaluation.domain.errors import ReleaseBlockedError
from app.continuous_evaluation.domain.models import (
    Benchmark,
    CalibrationAnalysis,
    EvaluationSuite,
    HumanEvaluation,
    ProductionSample,
    QualityGateResult,
    QualityGateRule,
    RegressionFinding,
)


class MockContinuousEvaluationRepository:
    """In-memory mock repository implementing ContinuousEvaluationRepositoryProtocol."""

    def __init__(self) -> None:
        self.benchmarks: dict[uuid.UUID, Benchmark] = {}
        self.suites: dict[uuid.UUID, EvaluationSuite] = {}
        self.quality_gates: dict[uuid.UUID, dict[str, Any]] = {}
        self.quality_gate_results: list[tuple[uuid.UUID, QualityGateResult]] = []
        self.regressions: list[tuple[uuid.UUID, RegressionFinding]] = []
        self.calibrations: dict[tuple[uuid.UUID, uuid.UUID], CalibrationAnalysis] = {}
        self.production_samples: dict[uuid.UUID, ProductionSample] = {}
        self.human_evaluations: list[HumanEvaluation] = []

    async def create_benchmark(self, benchmark: Benchmark) -> Benchmark:
        self.benchmarks[benchmark.id] = benchmark
        return benchmark

    async def get_benchmark(
        self, benchmark_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Benchmark | None:
        b = self.benchmarks.get(benchmark_id)
        if b and b.organization_id == organization_id:
            return b
        return None

    async def list_benchmarks(
        self,
        organization_id: uuid.UUID,
        target: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Benchmark]:
        items = [b for b in self.benchmarks.values() if b.organization_id == organization_id]
        if target:
            items = [b for b in items if b.target.value == target]
        if task_type:
            items = [b for b in items if b.task_type == task_type]
        return items[offset : offset + limit]

    async def update_benchmark_baseline(
        self, benchmark_id: uuid.UUID, baseline_run_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Benchmark:
        b = await self.get_benchmark(benchmark_id, organization_id)
        if not b:
            raise ValueError("Not found")
        b.baseline_run_id = baseline_run_id
        return b

    async def create_suite(self, suite: EvaluationSuite) -> EvaluationSuite:
        self.suites[suite.id] = suite
        return suite

    async def get_suite(
        self, suite_id: uuid.UUID, organization_id: uuid.UUID
    ) -> EvaluationSuite | None:
        s = self.suites.get(suite_id)
        if s and s.organization_id == organization_id:
            return s
        return None

    async def list_suites(
        self, organization_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[EvaluationSuite]:
        items = [s for s in self.suites.values() if s.organization_id == organization_id]
        return items[offset : offset + limit]

    async def create_quality_gate(
        self,
        organization_id: uuid.UUID,
        name: str,
        rules: dict[str, Any],
        description: str | None = None,
    ) -> uuid.UUID:
        gate_id = uuid.uuid4()
        self.quality_gates[gate_id] = {
            "id": str(gate_id),
            "organization_id": str(organization_id),
            "name": name,
            "description": description,
            "rules": rules,
            "status": "ACTIVE",
        }
        return gate_id

    async def get_quality_gate(
        self, gate_id: uuid.UUID, organization_id: uuid.UUID
    ) -> dict[str, Any] | None:
        g = self.quality_gates.get(gate_id)
        if g and g["organization_id"] == str(organization_id):
            return g
        return None

    async def list_quality_gates(
        self, organization_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        items = [
            g for g in self.quality_gates.values() if g["organization_id"] == str(organization_id)
        ]
        return items[offset : offset + limit]

    async def record_quality_gate_result(
        self, result: QualityGateResult, organization_id: uuid.UUID
    ) -> None:
        self.quality_gate_results.append((organization_id, result))

    async def list_quality_gate_results(
        self,
        organization_id: uuid.UUID,
        run_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[QualityGateResult]:
        items = [r for org, r in self.quality_gate_results if org == organization_id]
        if run_id:
            items = [r for r in items if r.run_id == run_id]
        return items[offset : offset + limit]

    async def record_regressions(
        self, regressions: list[RegressionFinding], organization_id: uuid.UUID
    ) -> None:
        for r in regressions:
            self.regressions.append((organization_id, r))

    async def list_regressions(
        self,
        organization_id: uuid.UUID,
        run_id: uuid.UUID | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RegressionFinding]:
        items = [r for org, r in self.regressions if org == organization_id]
        if run_id:
            items = [r for r in items if r.run_id == run_id]
        if severity:
            items = [r for r in items if r.severity.value == severity]
        return items[offset : offset + limit]

    async def record_calibration(
        self, calibration: CalibrationAnalysis, organization_id: uuid.UUID
    ) -> None:
        self.calibrations[(calibration.run_id, organization_id)] = calibration

    async def get_calibration(
        self, run_id: uuid.UUID, organization_id: uuid.UUID
    ) -> CalibrationAnalysis | None:
        return self.calibrations.get((run_id, organization_id))

    async def record_production_sample(self, sample: ProductionSample) -> ProductionSample:
        self.production_samples[sample.id] = sample
        return sample

    async def list_production_samples(
        self,
        organization_id: uuid.UUID,
        strategy: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProductionSample]:
        items = [
            s for s in self.production_samples.values() if s.organization_id == organization_id
        ]
        if strategy:
            items = [s for s in items if s.sampling_strategy.value == strategy]
        return items[offset : offset + limit]

    async def delete_expired_samples(self) -> int:
        now = datetime.now(UTC)
        expired = [sid for sid, s in self.production_samples.items() if s.expires_at <= now]
        for sid in expired:
            del self.production_samples[sid]
        return len(expired)

    async def record_human_evaluation(self, human_eval: HumanEvaluation) -> HumanEvaluation:
        self.human_evaluations.append(human_eval)
        return human_eval

    async def list_human_evaluations(
        self,
        organization_id: uuid.UUID,
        sample_id: uuid.UUID | None = None,
        case_result_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[HumanEvaluation]:
        items = [h for h in self.human_evaluations if h.organization_id == organization_id]
        if sample_id:
            items = [h for h in items if h.sample_id == sample_id]
        if case_result_id:
            items = [h for h in items if h.case_result_id == case_result_id]
        return items[offset : offset + limit]


# =========================================================================
# Unit Tests
# =========================================================================


def test_metric_registry_defaults_and_weights() -> None:
    """Test standard metric registration, custom weights, and normalization."""
    registry = MetricRegistry()
    assert registry.get_metric("groundedness") is not None
    assert registry.get_metric("citation_precision") is not None
    assert registry.get_metric("sql_validity") is not None

    weights = registry.get_category_weights()
    assert abs(sum(weights.values()) - 1.0) < 1e-5
    assert weights["grounding"] == 0.20
    assert weights["retrieval"] == 0.15

    # Update category weights
    new_weights = registry.update_category_weights(
        {"grounding": 30.0, "sql": 30.0, "retrieval": 40.0}
    )
    assert abs(sum(new_weights.values()) - 1.0) < 1e-5
    assert round(new_weights["grounding"], 2) == 0.30


def test_quality_score_computation() -> None:
    """Verify deterministic calculation of composite quality score."""
    registry = MetricRegistry()
    metrics = {
        "groundedness": 0.95,
        "citation_precision": 0.90,
        "retrieval_recall@5": 0.88,
        "sql_accuracy": 1.0,
        "semantic_accuracy": 0.92,
        "graph_grounding": 0.85,
        "faithfulness": 0.95,
        "latency_p95": 1200.0,
        "cost_per_query": 0.015,
    }
    score = registry.compute_composite_score(metrics)
    assert 0.85 <= score.overall_score <= 1.0
    assert "grounding" in score.breakdown
    assert score.breakdown["grounding"] == 0.95


@pytest.mark.asyncio
async def test_benchmark_and_suite_lifecycle() -> None:
    """Test benchmark creation, baseline updates, and suite packaging."""
    repo = MockContinuousEvaluationRepository()
    service = BenchmarkService(repo)
    org_id = uuid.uuid4()
    dataset_id = uuid.uuid4()

    benchmark = await service.create_benchmark(
        organization_id=org_id,
        name="Enterprise RAG Benchmark",
        task_type="RAG",
        target=EvaluationTarget.RAG,
        dataset_id=dataset_id,
        version=1,
    )
    assert benchmark.name == "Enterprise RAG Benchmark"
    assert benchmark.version == 1

    # Baseline update
    run_id = uuid.uuid4()
    updated = await service.set_baseline_run(benchmark.id, run_id, org_id)
    assert updated.baseline_run_id == run_id

    # Suite creation
    suite = await service.create_suite(
        organization_id=org_id,
        name="Enterprise Regression Suite v3",
        benchmark_ids=[str(benchmark.id)],
        version=1,
    )
    assert suite.name == "Enterprise Regression Suite v3"
    assert len(suite.benchmark_ids) == 1


def test_significance_analyzer() -> None:
    """Test statistical significance testing and sample size gating."""
    analyzer = SignificanceAnalyzer(min_samples=10)

    # Insufficient sample (< 10)
    is_sig, p_val, note = analyzer.analyze_paired_difference([0.9, 0.8], [0.7, 0.6])
    assert not is_sig
    assert p_val is None
    assert note == "INSUFFICIENT_SAMPLE"

    # Sufficient sample with significant drop
    baseline = [0.95] * 15
    candidate = [0.60] * 15  # Consistent drop
    is_sig, p_val, note = analyzer.analyze_paired_difference(baseline, candidate)
    # Zero variance in difference
    assert note == "ZERO_VARIANCE"

    # With varying differences
    import random

    random.seed(42)
    b_vals = [0.90 + random.uniform(-0.02, 0.02) for _ in range(25)]
    c_vals = [0.75 + random.uniform(-0.02, 0.02) for _ in range(25)]
    is_sig, p_val, note = analyzer.analyze_paired_difference(b_vals, c_vals)
    assert is_sig
    assert p_val is not None
    assert p_val < 0.01
    assert note == "STATISTICALLY_SIGNIFICANT"


@pytest.mark.asyncio
async def test_regression_service_severity_classification() -> None:
    """Test regression detection and multi-tier severity mappings."""
    repo = MockContinuousEvaluationRepository()
    service = RegressionService(repo)

    assert service.classify_severity(0.005) is None
    assert service.classify_severity(0.015) == RegressionSeverity.INFO
    assert service.classify_severity(0.035) == RegressionSeverity.WARNING
    assert service.classify_severity(0.06) == RegressionSeverity.MAJOR
    assert service.classify_severity(0.12) == RegressionSeverity.CRITICAL

    # Test regression detection against metrics
    org_id = uuid.uuid4()
    benchmark_id = uuid.uuid4()
    run_id = uuid.uuid4()
    baseline_run_id = uuid.uuid4()

    baseline_metrics = {
        "groundedness": 0.95,
        "citation_precision": 0.92,
        "retrieval_recall@5": 0.85,
    }
    # 10% drop on groundedness -> CRITICAL
    candidate_metrics = {
        "groundedness": 0.80,
        "citation_precision": 0.90,
        "retrieval_recall@5": 0.85,
    }

    findings = await service.detect_regressions(
        benchmark_id=benchmark_id,
        run_id=run_id,
        baseline_run_id=baseline_run_id,
        organization_id=org_id,
        baseline_metrics=baseline_metrics,
        candidate_metrics=candidate_metrics,
    )
    assert len(findings) >= 1
    grounding_finding = next(f for f in findings if f.metric_name == "groundedness")
    assert grounding_finding.severity == RegressionSeverity.CRITICAL
    assert grounding_finding.drop_percentage > 15.0


@pytest.mark.asyncio
async def test_quality_gate_evaluation() -> None:
    """Test Quality Gate thresholds and decision outcomes."""
    repo = MockContinuousEvaluationRepository()
    service = QualityGateService(repo)
    org_id = uuid.uuid4()
    run_id = uuid.uuid4()

    rules = [
        QualityGateRule(metric_name="groundedness", min_threshold=0.90, is_critical=True),
        QualityGateRule(metric_name="citation_precision", min_threshold=0.85, is_critical=False),
        QualityGateRule(metric_name="sql_accuracy", min_threshold=0.95, is_critical=True),
    ]
    gate_id = await service.create_gate(org_id, "Standard Production Gate", rules)

    # Passing scorecard
    passing_scorecard = {
        "metrics": {"groundedness": 0.95, "citation_precision": 0.90, "sql_accuracy": 0.98}
    }
    res_pass = await service.evaluate_gate(gate_id, run_id, passing_scorecard, org_id)
    assert res_pass.decision == QualityGateDecision.PASS
    assert len(res_pass.violations) == 0

    # Non-critical failure (warn/fail)
    warn_scorecard = {
        "metrics": {"groundedness": 0.92, "citation_precision": 0.80, "sql_accuracy": 0.96}
    }
    res_warn = await service.evaluate_gate(gate_id, run_id, warn_scorecard, org_id)
    assert res_warn.decision == QualityGateDecision.FAIL
    assert len(res_warn.violations) == 1

    # Critical breach -> BLOCK_RELEASE
    critical_scorecard = {
        "metrics": {"groundedness": 0.75, "citation_precision": 0.88, "sql_accuracy": 0.96}
    }
    res_block = await service.evaluate_gate(gate_id, run_id, critical_scorecard, org_id)
    assert res_block.decision == QualityGateDecision.BLOCK_RELEASE


def test_confidence_calibration() -> None:
    """Test Expected Calibration Error (ECE) and Brier Score computation."""
    repo = MockContinuousEvaluationRepository()
    service = CalibrationService(repo)
    run_id = uuid.uuid4()

    # Perfectly calibrated predictions
    predictions = [(0.9, True), (0.9, True), (0.9, True), (0.1, False), (0.1, False)]
    cal = service.compute_calibration(run_id, predictions, num_buckets=5)
    assert cal.run_id == run_id
    assert cal.ece >= 0.0
    assert cal.brier_score >= 0.0
    assert len(cal.buckets) == 5


def test_differential_comparison() -> None:
    """Test multi-version comparison across models and prompt versions."""
    service = ComparisonService()
    baseline = {
        "segmented_scores": {"quality_score": 0.82},
        "latency": {"p95_ms": 1500.0},
        "cost": {"cost_per_query_usd": 0.03},
        "metrics": {"groundedness": 0.85},
    }
    candidate = {
        "segmented_scores": {"quality_score": 0.92},
        "latency": {"p95_ms": 1200.0},
        "cost": {"cost_per_query_usd": 0.02},
        "metrics": {"groundedness": 0.94},
    }
    report = service.compare_scorecards(
        comparison_type="MODEL",
        baseline_id="gpt-4o-mini",
        candidate_id="gemini-1.5-pro",
        baseline_scorecard=baseline,
        candidate_scorecard=candidate,
    )
    assert report.winner == "gemini-1.5-pro"
    assert report.metrics_diff["quality_score"]["delta"] == 0.10


def test_privacy_sanitizer() -> None:
    """Test PII and secret redaction on sensitive queries/responses."""
    dirty_text = "User john.doe@example.com with token Bearer sk-1234567890abcdef1234 and credit card 4111-2222-3333-4444"
    clean_text, redacted = PrivacySanitizer.sanitize(dirty_text)
    assert redacted is True
    assert "john.doe@example.com" not in clean_text
    assert "[REDACTED_EMAIL]" in clean_text
    assert "[REDACTED_SECRET]" in clean_text
    assert "[REDACTED_CC]" in clean_text


@pytest.mark.asyncio
async def test_production_sample_and_retention() -> None:
    """Test production sampling and retention purge."""
    repo = MockContinuousEvaluationRepository()
    service = MonitoringService(repo, default_retention_days=1)
    org_id = uuid.uuid4()

    sample = await service.capture_production_sample(
        organization_id=org_id,
        query="What is the price for john.doe@corp.com?",
        response="Your balance is $500",
        strategy=SamplingStrategy.RISK_BASED,
        retention_days=0,  # Immediately expired
    )
    assert sample.redacted is True
    assert "[REDACTED_EMAIL]" in sample.query

    # Test purging expired
    purged_count = await service.purge_expired_samples()
    assert purged_count == 1
    assert len(repo.production_samples) == 0


def test_release_quality_policy_and_agent_block() -> None:
    """Ensure release policy blocks releases on critical failures and rejects autonomous agent approval."""
    policy = ReleaseQualityPolicy()
    gate_id = uuid.uuid4()
    run_id = uuid.uuid4()

    # Autonomous agent attempt -> strictly blocked
    with pytest.raises(ReleaseBlockedError, match="Autonomous agents cannot approve"):
        policy.enforce_release([], approver_is_agent=True)

    # Gated on critical failure
    critical_res = QualityGateResult(
        gate_id=gate_id,
        run_id=run_id,
        decision=QualityGateDecision.BLOCK_RELEASE,
        scorecard={},
        violations=[{"type": "CRITICAL_DROP"}],
    )
    with pytest.raises(ReleaseBlockedError, match="Critical quality gate"):
        policy.enforce_release([critical_res], approver_is_agent=False)

    # Approved when passed
    passed_res = QualityGateResult(
        gate_id=gate_id,
        run_id=run_id,
        decision=QualityGateDecision.PASS,
        scorecard={},
        violations=[],
    )
    status, msg = policy.evaluate_release_decision([passed_res], approver_is_agent=False)
    assert status == ReleaseStatus.APPROVED
    assert "All quality gates passed" in msg

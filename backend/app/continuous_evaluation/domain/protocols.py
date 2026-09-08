"""Domain protocol interfaces for Enterprise Continuous AI Evaluation."""

import uuid
from typing import Any, Protocol, runtime_checkable

from app.continuous_evaluation.domain.models import (
    Benchmark,
    CalibrationAnalysis,
    ComparisonReport,
    EvaluationSuite,
    HumanEvaluation,
    ProductionSample,
    QualityGateResult,
    QualityScore,
    RegressionFinding,
)


@runtime_checkable
class ContinuousEvaluationRepositoryProtocol(Protocol):
    """Persistence protocol for all continuous evaluation entities with tenant isolation."""

    # Benchmark operations
    async def create_benchmark(self, benchmark: Benchmark) -> Benchmark: ...
    async def get_benchmark(
        self, benchmark_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Benchmark | None: ...
    async def list_benchmarks(
        self,
        organization_id: uuid.UUID,
        target: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Benchmark]: ...
    async def update_benchmark_baseline(
        self, benchmark_id: uuid.UUID, baseline_run_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Benchmark: ...

    # Evaluation Suite operations
    async def create_suite(self, suite: EvaluationSuite) -> EvaluationSuite: ...
    async def get_suite(
        self, suite_id: uuid.UUID, organization_id: uuid.UUID
    ) -> EvaluationSuite | None: ...
    async def list_suites(
        self, organization_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[EvaluationSuite]: ...

    # Quality Gate operations
    async def create_quality_gate(
        self,
        organization_id: uuid.UUID,
        name: str,
        rules: dict[str, Any],
        description: str | None = None,
    ) -> uuid.UUID: ...
    async def get_quality_gate(
        self, gate_id: uuid.UUID, organization_id: uuid.UUID
    ) -> dict[str, Any] | None: ...
    async def list_quality_gates(
        self, organization_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]: ...
    async def record_quality_gate_result(
        self, result: QualityGateResult, organization_id: uuid.UUID
    ) -> None: ...
    async def list_quality_gate_results(
        self,
        organization_id: uuid.UUID,
        run_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[QualityGateResult]: ...

    # Regression operations
    async def record_regressions(
        self, regressions: list[RegressionFinding], organization_id: uuid.UUID
    ) -> None: ...
    async def list_regressions(
        self,
        organization_id: uuid.UUID,
        run_id: uuid.UUID | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RegressionFinding]: ...

    # Calibration operations
    async def record_calibration(
        self, calibration: CalibrationAnalysis, organization_id: uuid.UUID
    ) -> None: ...
    async def get_calibration(
        self, run_id: uuid.UUID, organization_id: uuid.UUID
    ) -> CalibrationAnalysis | None: ...

    # Production sampling operations
    async def record_production_sample(self, sample: ProductionSample) -> ProductionSample: ...
    async def list_production_samples(
        self,
        organization_id: uuid.UUID,
        strategy: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProductionSample]: ...
    async def delete_expired_samples(self) -> int: ...

    # Human evaluation operations
    async def record_human_evaluation(self, human_eval: HumanEvaluation) -> HumanEvaluation: ...
    async def list_human_evaluations(
        self,
        organization_id: uuid.UUID,
        sample_id: uuid.UUID | None = None,
        case_result_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[HumanEvaluation]: ...


@runtime_checkable
class QualityScoringProtocol(Protocol):
    """Protocol for calculating composite quality scores across dimensions."""

    def compute_quality_score(
        self, metrics: dict[str, float], custom_weights: dict[str, float] | None = None
    ) -> QualityScore: ...


@runtime_checkable
class RegressionDetectorProtocol(Protocol):
    """Protocol for detecting regressions against baseline runs with statistical significance."""

    async def detect_regressions(
        self,
        candidate_run_id: uuid.UUID,
        baseline_run_id: uuid.UUID,
        benchmark_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> list[RegressionFinding]: ...


@runtime_checkable
class QualityGateServiceProtocol(Protocol):
    """Protocol for evaluating quality gate rules against evaluation scorecards."""

    async def evaluate_gate(
        self,
        gate_id: uuid.UUID,
        run_id: uuid.UUID,
        scorecard: dict[str, Any],
        organization_id: uuid.UUID,
        regressions: list[RegressionFinding] | None = None,
    ) -> QualityGateResult: ...


@runtime_checkable
class CalibrationServiceProtocol(Protocol):
    """Protocol for computing confidence calibration, ECE, and Brier score."""

    def compute_calibration(
        self,
        run_id: uuid.UUID,
        predictions: list[tuple[float, bool]],  # list of (confidence, is_correct)
        num_buckets: int = 10,
    ) -> CalibrationAnalysis: ...


@runtime_checkable
class ComparisonServiceProtocol(Protocol):
    """Protocol for comparative evaluation of models, prompts, and semantic/graph schemas."""

    async def compare_runs(
        self,
        comparison_type: str,
        baseline_run_id: uuid.UUID,
        candidate_run_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> ComparisonReport: ...


@runtime_checkable
class ProductionQualityMonitorProtocol(Protocol):
    """Protocol for sampling production executions safely under retention and privacy rules."""

    async def capture_production_sample(
        self,
        organization_id: uuid.UUID,
        query: str,
        response: str,
        strategy: str,
        data_sensitivity: str,
        retention_days: int,
        source_execution_id: str | None = None,
    ) -> ProductionSample: ...

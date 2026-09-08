"""SQLAlchemy repository implementation for Enterprise Continuous AI Evaluation."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.continuous_evaluation.domain.enums import (
    EvaluationSource,
    EvaluationTarget,
    QualityGateDecision,
    RegressionSeverity,
    SamplingStrategy,
)
from app.continuous_evaluation.domain.models import (
    Benchmark,
    CalibrationAnalysis,
    CalibrationBucket,
    EvaluationSuite,
    HumanEvaluation,
    ProductionSample,
    QualityGateResult,
    RegressionFinding,
)
from app.continuous_evaluation.domain.protocols import ContinuousEvaluationRepositoryProtocol
from app.models.continuous_evaluation import (
    BenchmarkModel,
    CalibrationResultModel,
    EvaluationSuiteModel,
    HumanEvaluationModel,
    ProductionEvaluationSampleModel,
    QualityGateModel,
    QualityGateResultModel,
    RegressionModel,
)


class ContinuousEvaluationRepository(ContinuousEvaluationRepositoryProtocol):
    """Repository handling all continuous evaluation persistence operations with strict tenant isolation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Benchmarks ---

    async def create_benchmark(self, benchmark: Benchmark) -> Benchmark:
        model = BenchmarkModel(
            id=benchmark.id,
            organization_id=benchmark.organization_id,
            name=benchmark.name,
            description=benchmark.description,
            task_type=benchmark.task_type,
            target=benchmark.target.value
            if isinstance(benchmark.target, EvaluationTarget)
            else benchmark.target,
            dataset_id=benchmark.dataset_id,
            version=benchmark.version,
            baseline_run_id=benchmark.baseline_run_id,
            status=benchmark.status,
        )
        self.session.add(model)
        await self.session.flush()
        return self._to_domain_benchmark(model)

    async def get_benchmark(
        self, benchmark_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Benchmark | None:
        stmt = select(BenchmarkModel).where(
            BenchmarkModel.id == benchmark_id,
            BenchmarkModel.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        return self._to_domain_benchmark(model) if model else None

    async def list_benchmarks(
        self,
        organization_id: uuid.UUID,
        target: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Benchmark]:
        stmt = select(BenchmarkModel).where(BenchmarkModel.organization_id == organization_id)
        if target:
            stmt = stmt.where(BenchmarkModel.target == target)
        if task_type:
            stmt = stmt.where(BenchmarkModel.task_type == task_type)
        stmt = stmt.order_by(BenchmarkModel.created_at.desc()).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return [self._to_domain_benchmark(m) for m in res.scalars().all()]

    async def update_benchmark_baseline(
        self, benchmark_id: uuid.UUID, baseline_run_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Benchmark:
        stmt = select(BenchmarkModel).where(
            BenchmarkModel.id == benchmark_id,
            BenchmarkModel.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if not model:
            raise ValueError(
                f"Benchmark {benchmark_id} not found for organization {organization_id}"
            )
        model.baseline_run_id = baseline_run_id
        await self.session.flush()
        return self._to_domain_benchmark(model)

    # --- Evaluation Suites ---

    async def create_suite(self, suite: EvaluationSuite) -> EvaluationSuite:
        model = EvaluationSuiteModel(
            id=suite.id,
            organization_id=suite.organization_id,
            name=suite.name,
            description=suite.description,
            benchmark_ids=suite.benchmark_ids,
            version=suite.version,
            status=suite.status,
        )
        self.session.add(model)
        await self.session.flush()
        return self._to_domain_suite(model)

    async def get_suite(
        self, suite_id: uuid.UUID, organization_id: uuid.UUID
    ) -> EvaluationSuite | None:
        stmt = select(EvaluationSuiteModel).where(
            EvaluationSuiteModel.id == suite_id,
            EvaluationSuiteModel.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        return self._to_domain_suite(model) if model else None

    async def list_suites(
        self, organization_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[EvaluationSuite]:
        stmt = (
            select(EvaluationSuiteModel)
            .where(EvaluationSuiteModel.organization_id == organization_id)
            .order_by(EvaluationSuiteModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return [self._to_domain_suite(m) for m in res.scalars().all()]

    # --- Quality Gates ---

    async def create_quality_gate(
        self,
        organization_id: uuid.UUID,
        name: str,
        rules: dict[str, Any],
        description: str | None = None,
    ) -> uuid.UUID:
        gate_id = uuid.uuid4()
        model = QualityGateModel(
            id=gate_id,
            organization_id=organization_id,
            name=name,
            description=description,
            rules=rules,
            status="ACTIVE",
        )
        self.session.add(model)
        await self.session.flush()
        return gate_id

    async def get_quality_gate(
        self, gate_id: uuid.UUID, organization_id: uuid.UUID
    ) -> dict[str, Any] | None:
        stmt = select(QualityGateModel).where(
            QualityGateModel.id == gate_id,
            QualityGateModel.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if not model:
            return None
        return {
            "id": str(model.id),
            "organization_id": str(model.organization_id),
            "name": model.name,
            "description": model.description,
            "rules": model.rules,
            "status": model.status,
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }

    async def list_quality_gates(
        self, organization_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        stmt = (
            select(QualityGateModel)
            .where(QualityGateModel.organization_id == organization_id)
            .order_by(QualityGateModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return [
            {
                "id": str(m.id),
                "organization_id": str(m.organization_id),
                "name": m.name,
                "description": m.description,
                "rules": m.rules,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in res.scalars().all()
        ]

    async def record_quality_gate_result(
        self, result: QualityGateResult, organization_id: uuid.UUID
    ) -> None:
        model = QualityGateResultModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            gate_id=result.gate_id,
            run_id=result.run_id,
            decision=result.decision.value
            if isinstance(result.decision, QualityGateDecision)
            else result.decision,
            scorecard=result.scorecard,
            violations=result.violations,
        )
        self.session.add(model)
        await self.session.flush()

    async def list_quality_gate_results(
        self,
        organization_id: uuid.UUID,
        run_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[QualityGateResult]:
        stmt = select(QualityGateResultModel).where(
            QualityGateResultModel.organization_id == organization_id
        )
        if run_id:
            stmt = stmt.where(QualityGateResultModel.run_id == run_id)
        stmt = stmt.order_by(QualityGateResultModel.created_at.desc()).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return [
            QualityGateResult(
                gate_id=m.gate_id,
                run_id=m.run_id,
                decision=QualityGateDecision(m.decision),
                scorecard=m.scorecard,
                violations=m.violations,
            )
            for m in res.scalars().all()
        ]

    # --- Regressions ---

    async def record_regressions(
        self, regressions: list[RegressionFinding], organization_id: uuid.UUID
    ) -> None:
        for r in regressions:
            model = RegressionModel(
                id=uuid.uuid4(),
                organization_id=organization_id,
                benchmark_id=r.benchmark_id,
                run_id=r.run_id,
                baseline_run_id=r.baseline_run_id,
                severity=r.severity.value
                if isinstance(r.severity, RegressionSeverity)
                else r.severity,
                metric_name=r.metric_name,
                baseline_value=r.baseline_value,
                current_value=r.current_value,
                drop_percentage=r.drop_percentage,
                details=r.details,
            )
            self.session.add(model)
        await self.session.flush()

    async def list_regressions(
        self,
        organization_id: uuid.UUID,
        run_id: uuid.UUID | None = None,
        severity: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RegressionFinding]:
        stmt = select(RegressionModel).where(RegressionModel.organization_id == organization_id)
        if run_id:
            stmt = stmt.where(RegressionModel.run_id == run_id)
        if severity:
            stmt = stmt.where(RegressionModel.severity == severity)
        stmt = stmt.order_by(RegressionModel.created_at.desc()).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return [
            RegressionFinding(
                benchmark_id=m.benchmark_id,
                run_id=m.run_id,
                baseline_run_id=m.baseline_run_id,
                metric_name=m.metric_name,
                baseline_value=m.baseline_value,
                current_value=m.current_value,
                drop_percentage=m.drop_percentage,
                severity=RegressionSeverity(m.severity),
                details=m.details,
            )
            for m in res.scalars().all()
        ]

    # --- Calibration ---

    async def record_calibration(
        self, calibration: CalibrationAnalysis, organization_id: uuid.UUID
    ) -> None:
        model = CalibrationResultModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            run_id=calibration.run_id,
            ece=calibration.ece,
            brier_score=calibration.brier_score,
            reliability_buckets=[b.to_dict() for b in calibration.buckets],
        )
        self.session.add(model)
        await self.session.flush()

    async def get_calibration(
        self, run_id: uuid.UUID, organization_id: uuid.UUID
    ) -> CalibrationAnalysis | None:
        stmt = select(CalibrationResultModel).where(
            CalibrationResultModel.run_id == run_id,
            CalibrationResultModel.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        model = res.scalar_one_or_none()
        if not model:
            return None
        buckets = [
            CalibrationBucket(
                bin_start=b["bin_start"],
                bin_end=b["bin_end"],
                avg_confidence=b["avg_confidence"],
                accuracy=b["accuracy"],
                sample_count=b["sample_count"],
            )
            for b in model.reliability_buckets
        ]
        return CalibrationAnalysis(
            run_id=model.run_id,
            ece=model.ece,
            brier_score=model.brier_score,
            buckets=buckets,
        )

    # --- Production Samples ---

    async def record_production_sample(self, sample: ProductionSample) -> ProductionSample:
        model = ProductionEvaluationSampleModel(
            id=sample.id,
            organization_id=sample.organization_id,
            source_execution_id=sample.source_execution_id,
            query=sample.query,
            response=sample.response,
            sampling_strategy=sample.sampling_strategy.value
            if isinstance(sample.sampling_strategy, SamplingStrategy)
            else sample.sampling_strategy,
            data_sensitivity=sample.data_sensitivity,
            redacted=sample.redacted,
            expires_at=sample.expires_at,
        )
        self.session.add(model)
        await self.session.flush()
        return self._to_domain_sample(model)

    async def list_production_samples(
        self,
        organization_id: uuid.UUID,
        strategy: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProductionSample]:
        stmt = select(ProductionEvaluationSampleModel).where(
            ProductionEvaluationSampleModel.organization_id == organization_id
        )
        if strategy:
            stmt = stmt.where(ProductionEvaluationSampleModel.sampling_strategy == strategy)
        stmt = (
            stmt.order_by(ProductionEvaluationSampleModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return [self._to_domain_sample(m) for m in res.scalars().all()]

    async def delete_expired_samples(self) -> int:
        now = datetime.now(UTC)
        stmt = delete(ProductionEvaluationSampleModel).where(
            ProductionEvaluationSampleModel.expires_at <= now
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        count = getattr(res, "rowcount", 0) or 0
        return int(count)

    # --- Human Evaluations ---

    async def record_human_evaluation(self, human_eval: HumanEvaluation) -> HumanEvaluation:
        model = HumanEvaluationModel(
            id=human_eval.id,
            organization_id=human_eval.organization_id,
            sample_id=human_eval.sample_id,
            case_result_id=human_eval.case_result_id,
            evaluator_id=human_eval.evaluator_id,
            accuracy_score=human_eval.accuracy_score,
            helpfulness_score=human_eval.helpfulness_score,
            grounding_score=human_eval.grounding_score,
            clarity_score=human_eval.clarity_score,
            comments=human_eval.comments,
        )
        self.session.add(model)
        await self.session.flush()
        return self._to_domain_human_eval(model)

    async def list_human_evaluations(
        self,
        organization_id: uuid.UUID,
        sample_id: uuid.UUID | None = None,
        case_result_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[HumanEvaluation]:
        stmt = select(HumanEvaluationModel).where(
            HumanEvaluationModel.organization_id == organization_id
        )
        if sample_id:
            stmt = stmt.where(HumanEvaluationModel.sample_id == sample_id)
        if case_result_id:
            stmt = stmt.where(HumanEvaluationModel.case_result_id == case_result_id)
        stmt = stmt.order_by(HumanEvaluationModel.created_at.desc()).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return [self._to_domain_human_eval(m) for m in res.scalars().all()]

    # --- Private mappers ---

    def _to_domain_benchmark(self, model: BenchmarkModel) -> Benchmark:
        return Benchmark(
            id=model.id,
            organization_id=model.organization_id,
            name=model.name,
            description=model.description,
            task_type=model.task_type,
            target=EvaluationTarget(model.target),
            dataset_id=model.dataset_id,
            version=model.version,
            baseline_run_id=model.baseline_run_id,
            status=model.status,
            created_at=model.created_at,
        )

    def _to_domain_suite(self, model: EvaluationSuiteModel) -> EvaluationSuite:
        return EvaluationSuite(
            id=model.id,
            organization_id=model.organization_id,
            name=model.name,
            description=model.description,
            benchmark_ids=model.benchmark_ids,
            version=model.version,
            status=model.status,
            created_at=model.created_at,
        )

    def _to_domain_sample(self, model: ProductionEvaluationSampleModel) -> ProductionSample:
        return ProductionSample(
            id=model.id,
            organization_id=model.organization_id,
            source_execution_id=model.source_execution_id,
            query=model.query,
            response=model.response,
            sampling_strategy=SamplingStrategy(model.sampling_strategy),
            data_sensitivity=model.data_sensitivity,
            redacted=model.redacted,
            expires_at=model.expires_at,
            created_at=model.created_at,
        )

    def _to_domain_human_eval(self, model: HumanEvaluationModel) -> HumanEvaluation:
        return HumanEvaluation(
            id=model.id,
            organization_id=model.organization_id,
            sample_id=model.sample_id,
            case_result_id=model.case_result_id,
            evaluator_id=model.evaluator_id,
            accuracy_score=model.accuracy_score,
            helpfulness_score=model.helpfulness_score,
            grounding_score=model.grounding_score,
            clarity_score=model.clarity_score,
            comments=model.comments,
            created_at=model.created_at,
            evaluation_source=EvaluationSource.HUMAN,
        )

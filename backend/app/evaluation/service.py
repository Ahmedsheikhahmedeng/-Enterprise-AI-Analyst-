import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.service import AIAnalystService
from app.evaluation.benchmark import BenchmarkRunner
from app.evaluation.cases import CaseManager
from app.evaluation.config import EvaluationConfig, get_evaluation_config
from app.evaluation.dataset import DatasetManager
from app.evaluation.exceptions import (
    EvaluationAuthorizationError,
    EvaluationRunNotFoundError,
)
from app.evaluation.models import RegressionReport, Scorecard
from app.evaluation.regression import RegressionDetector
from app.evaluation.scorecard import ScorecardGenerator
from app.models.audit import AuditLog
from app.models.evaluation import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationDataset,
    EvaluationRun,
)

logger = logging.getLogger(__name__)


class EvaluationService:
    """Enterprise evaluation facade coordinating datasets, benchmarks, scorecards, and audits."""

    def __init__(
        self,
        config: EvaluationConfig | None = None,
        dataset_manager: DatasetManager | None = None,
        case_manager: CaseManager | None = None,
        benchmark_runner: BenchmarkRunner | None = None,
        scorecard_generator: ScorecardGenerator | None = None,
        regression_detector: RegressionDetector | None = None,
    ) -> None:
        self.config = config or get_evaluation_config()
        self.dataset_manager = dataset_manager or DatasetManager()
        self.case_manager = case_manager or CaseManager()
        self.benchmark_runner = benchmark_runner or BenchmarkRunner(self.config)
        self.scorecard_generator = scorecard_generator or ScorecardGenerator(self.config)
        self.regression_detector = regression_detector or RegressionDetector(self.config)

    async def create_dataset(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        name: str,
        description: str | None = None,
        language: str = "en",
        user_id: UUID | None = None,
    ) -> EvaluationDataset:
        """Create a new dataset and emit audit trail."""
        dataset = await self.dataset_manager.create_dataset(
            session=session,
            organization_id=organization_id,
            name=name,
            description=description,
            language=language,
            user_id=user_id,
        )
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="evaluation.dataset_created",
            resource_type="evaluation_dataset",
            resource_id=str(dataset.id),
            metadata_={"name": dataset.name, "language": dataset.language},
        )
        session.add(audit)
        await session.commit()
        await session.refresh(dataset)
        return dataset

    async def get_dataset(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        dataset_id: UUID,
    ) -> EvaluationDataset:
        """Fetch dataset enforcing tenant isolation."""
        return await self.dataset_manager.get_dataset(
            session=session,
            organization_id=organization_id,
            dataset_id=dataset_id,
        )

    async def list_datasets(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EvaluationDataset], int]:
        """List datasets belonging to organization."""
        return await self.dataset_manager.list_datasets(
            session=session,
            organization_id=organization_id,
            page=page,
            page_size=page_size,
        )

    async def add_case(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        dataset_id: UUID,
        query: str,
        route_expected: str,
        language: str = "en",
        datasource_id: UUID | None = None,
        expected_answer: str | None = None,
        expected_citations: list[str] | None = None,
        expected_documents: list[str] | None = None,
        expected_sql_semantics: str | None = None,
        expected_metrics: dict[str, Any] | None = None,
        expected_rows: list[dict[str, Any]] | None = None,
        relevant_chunks: list[str] | None = None,
        tags: list[str] | None = None,
        difficulty: str = "medium",
        user_id: UUID | None = None,
    ) -> EvaluationCase:
        """Add a benchmark case and emit audit trail."""
        case = await self.case_manager.add_case(
            session=session,
            organization_id=organization_id,
            dataset_id=dataset_id,
            query=query,
            route_expected=route_expected,
            language=language,
            datasource_id=datasource_id,
            expected_answer=expected_answer,
            expected_citations=expected_citations,
            expected_documents=expected_documents,
            expected_sql_semantics=expected_sql_semantics,
            expected_metrics=expected_metrics,
            expected_rows=expected_rows,
            relevant_chunks=relevant_chunks,
            tags=tags,
            difficulty=difficulty,
        )
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="evaluation.case_created",
            resource_type="evaluation_case",
            resource_id=str(case.id),
            metadata_={"dataset_id": str(dataset_id), "route_expected": route_expected},
        )
        session.add(audit)
        await session.commit()
        await session.refresh(case)
        return case

    async def get_case(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        case_id: UUID,
    ) -> EvaluationCase:
        """Fetch evaluation case enforcing tenant isolation."""
        return await self.case_manager.get_case(
            session=session,
            organization_id=organization_id,
            case_id=case_id,
        )

    async def list_cases(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        dataset_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[EvaluationCase], int]:
        """List cases belonging to dataset under tenant isolation."""
        # Ensure dataset belongs to organization first
        await self.get_dataset(session, organization_id=organization_id, dataset_id=dataset_id)
        return await self.case_manager.list_cases(
            session=session,
            organization_id=organization_id,
            dataset_id=dataset_id,
            limit=limit,
            offset=offset,
        )

    async def run_benchmark(
        self,
        session: AsyncSession,
        *,
        analyst_service: AIAnalystService,
        organization_id: UUID,
        dataset_id: UUID,
        dataset_version: int | None = None,
        max_cases: int | None = None,
        tags: list[str] | None = None,
        user_id: UUID | None = None,
    ) -> tuple[EvaluationRun, list[EvaluationCaseResult]]:
        """Trigger benchmark evaluation run, record case outcomes, and emit audit trail."""
        run, results = await self.benchmark_runner.run_benchmark(
            session=session,
            analyst_service=analyst_service,
            organization_id=organization_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            max_cases=max_cases,
            tags=tags,
            user_id=user_id,
        )

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="evaluation.run_completed",
            resource_type="evaluation_run",
            resource_id=str(run.id),
            metadata_={
                "dataset_id": str(dataset_id),
                "total_cases": run.total_cases,
                "passed_cases": run.passed_cases,
                "failed_cases": run.failed_cases,
                "duration_ms": run.duration_ms,
            },
        )
        session.add(audit)
        await session.commit()
        await session.refresh(run)
        return run, results

    async def get_run(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        run_id: UUID,
    ) -> EvaluationRun:
        """Fetch evaluation run enforcing tenant isolation."""
        stmt = select(EvaluationRun).where(EvaluationRun.id == run_id)
        res = await session.execute(stmt)
        run = res.scalars().first()

        if not run:
            raise EvaluationRunNotFoundError(
                message=f"Evaluation run '{run_id}' not found.",
                details={"run_id": str(run_id)},
            )
        if run.organization_id != organization_id:
            raise EvaluationAuthorizationError(
                message="Cannot access evaluation run belonging to another organization.",
                details={"run_id": str(run_id)},
            )
        return run

    async def get_run_results(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        run_id: UUID,
    ) -> list[EvaluationCaseResult]:
        """Fetch all case results for an evaluation run."""
        await self.get_run(session, organization_id=organization_id, run_id=run_id)

        stmt = (
            select(EvaluationCaseResult)
            .where(
                EvaluationCaseResult.run_id == run_id,
                EvaluationCaseResult.organization_id == organization_id,
            )
            .order_by(EvaluationCaseResult.created_at.asc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_scorecard(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        run_id: UUID,
    ) -> Scorecard:
        """Calculate and return aggregated Scorecard for an evaluation run."""
        run = await self.get_run(session, organization_id=organization_id, run_id=run_id)
        results = await self.get_run_results(
            session, organization_id=organization_id, run_id=run_id
        )

        return self.scorecard_generator.generate(
            run_id=run.id,
            dataset_id=run.dataset_id,
            dataset_version=run.dataset_version,
            results=results,
        )

    async def compare_runs(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        baseline_run_id: UUID,
        candidate_run_id: UUID,
        user_id: UUID | None = None,
    ) -> RegressionReport:
        """Perform regression comparison between baseline and candidate benchmark runs."""
        b_scorecard = await self.get_scorecard(
            session, organization_id=organization_id, run_id=baseline_run_id
        )
        c_scorecard = await self.get_scorecard(
            session, organization_id=organization_id, run_id=candidate_run_id
        )

        b_results = await self.get_run_results(
            session, organization_id=organization_id, run_id=baseline_run_id
        )
        c_results = await self.get_run_results(
            session, organization_id=organization_id, run_id=candidate_run_id
        )

        report = self.regression_detector.compare_runs(
            baseline_scorecard=b_scorecard,
            candidate_scorecard=c_scorecard,
            baseline_results=b_results,
            candidate_results=c_results,
        )

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="evaluation.compared",
            resource_type="evaluation_run",
            resource_id=str(candidate_run_id),
            metadata_={
                "baseline_run_id": str(baseline_run_id),
                "status": report.status,
                "quality_delta": report.quality_delta,
            },
        )
        session.add(audit)
        await session.commit()
        return report

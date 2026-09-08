"""Task adapter for background benchmark evaluation runs."""

import uuid
from typing import Any

from app.jobs.context import JobContext
from app.jobs.exceptions import JobCancellationError, NonRetryableJobError
from app.workers.ingestion import get_worker_session_factory


class EvaluationTask:
    """Adapts BenchmarkRunner into standard TaskHandler interface."""

    def __init__(
        self,
        runner: Any = None,
        analyst_service: Any = None,
    ) -> None:
        self._runner = runner
        self._analyst_service = analyst_service
        self.session_factory = get_worker_session_factory()

    @property
    def runner(self) -> Any:
        if self._runner is None:
            from app.evaluation.benchmark import BenchmarkRunner

            self._runner = BenchmarkRunner()
        return self._runner

    @property
    def analyst_service(self) -> Any:
        if self._analyst_service is None:
            from app.analyst.service import AIAnalystService

            self._analyst_service = AIAnalystService()
        return self._analyst_service

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        """Execute benchmark evaluation suite in dedicated session."""
        raw_dataset_id = payload.get("dataset_id")
        if not raw_dataset_id:
            raise NonRetryableJobError("Missing required 'dataset_id' in job payload")

        try:
            dataset_id = uuid.UUID(str(raw_dataset_id))
        except ValueError as exc:
            raise NonRetryableJobError(f"Invalid dataset_id format: {raw_dataset_id}") from exc

        dataset_version = payload.get("dataset_version")
        max_cases = payload.get("max_cases")
        tags = payload.get("tags")

        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        context.report_progress(0.1, "Initializing benchmark evaluation")

        async with self.session_factory() as session:
            run_obj, case_results = await self.runner.run_benchmark(
                session=session,
                analyst_service=self.analyst_service,
                organization_id=context.organization_id,
                dataset_id=dataset_id,
                dataset_version=int(dataset_version) if dataset_version is not None else None,
                max_cases=int(max_cases) if max_cases is not None else None,
                tags=list(tags) if tags is not None else None,
                user_id=context.created_by,
            )
            await session.commit()

        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        context.report_progress(1.0, "Benchmark evaluation completed")

        pass_rate = (run_obj.passed_cases / run_obj.total_cases) if run_obj.total_cases > 0 else 0.0
        return {
            "dataset_id": str(dataset_id),
            "run_id": str(run_obj.id),
            "status": "completed",
            "total_cases": run_obj.total_cases,
            "passed_cases": run_obj.passed_cases,
            "failed_cases": run_obj.failed_cases,
            "score": round(pass_rate, 4),
            "duration_ms": run_obj.duration_ms,
        }

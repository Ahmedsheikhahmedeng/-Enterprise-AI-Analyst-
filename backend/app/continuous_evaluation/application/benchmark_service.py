"""Application service managing versioned benchmarks and evaluation suites."""

import uuid

from app.continuous_evaluation.domain.enums import EvaluationTarget
from app.continuous_evaluation.domain.errors import (
    BenchmarkNotFoundError,
    EvaluationSuiteNotFoundError,
)
from app.continuous_evaluation.domain.models import Benchmark, EvaluationSuite
from app.continuous_evaluation.domain.protocols import ContinuousEvaluationRepositoryProtocol
from app.observability.instrumentation.continuous_evaluation import (
    ContinuousEvaluationInstrumentation,
)


class BenchmarkService:
    """Coordinates lifecycle, baseline assignments, and suite packaging for benchmarks."""

    def __init__(
        self,
        repository: ContinuousEvaluationRepositoryProtocol,
        instrumentation: ContinuousEvaluationInstrumentation | None = None,
    ) -> None:
        self.repository = repository
        self.instrumentation = instrumentation

    async def create_benchmark(
        self,
        organization_id: uuid.UUID,
        name: str,
        task_type: str,
        target: EvaluationTarget,
        dataset_id: uuid.UUID,
        description: str | None = None,
        version: int = 1,
    ) -> Benchmark:
        """Creates a new versioned benchmark target."""
        benchmark_id = uuid.uuid4()
        benchmark = Benchmark(
            id=benchmark_id,
            organization_id=organization_id,
            name=name,
            description=description,
            task_type=task_type,
            target=target,
            dataset_id=dataset_id,
            version=version,
            status="ACTIVE",
        )
        created = await self.repository.create_benchmark(benchmark)
        return created

    async def get_benchmark(self, benchmark_id: uuid.UUID, organization_id: uuid.UUID) -> Benchmark:
        """Retrieves a benchmark ensuring tenant isolation."""
        benchmark = await self.repository.get_benchmark(benchmark_id, organization_id)
        if not benchmark:
            raise BenchmarkNotFoundError(f"Benchmark {benchmark_id} not found")
        return benchmark

    async def list_benchmarks(
        self,
        organization_id: uuid.UUID,
        target: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Benchmark]:
        """Lists benchmarks belonging to organization with optional filters."""
        return await self.repository.list_benchmarks(
            organization_id=organization_id,
            target=target,
            task_type=task_type,
            limit=limit,
            offset=offset,
        )

    async def set_baseline_run(
        self,
        benchmark_id: uuid.UUID,
        baseline_run_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Benchmark:
        """Sets or updates the baseline evaluation run for regression comparisons."""
        # Verify existence
        await self.get_benchmark(benchmark_id, organization_id)
        updated = await self.repository.update_benchmark_baseline(
            benchmark_id, baseline_run_id, organization_id
        )
        return updated

    # --- Evaluation Suite Management ---

    async def create_suite(
        self,
        organization_id: uuid.UUID,
        name: str,
        benchmark_ids: list[str],
        description: str | None = None,
        version: int = 1,
    ) -> EvaluationSuite:
        """Packages multiple benchmarks into an evaluation suite."""
        suite_id = uuid.uuid4()
        suite = EvaluationSuite(
            id=suite_id,
            organization_id=organization_id,
            name=name,
            description=description,
            benchmark_ids=benchmark_ids,
            version=version,
            status="ACTIVE",
        )
        return await self.repository.create_suite(suite)

    async def get_suite(self, suite_id: uuid.UUID, organization_id: uuid.UUID) -> EvaluationSuite:
        """Retrieves an evaluation suite by ID."""
        suite = await self.repository.get_suite(suite_id, organization_id)
        if not suite:
            raise EvaluationSuiteNotFoundError(f"Evaluation suite {suite_id} not found")
        return suite

    async def list_suites(
        self,
        organization_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EvaluationSuite]:
        """Lists suites belonging to organization."""
        return await self.repository.list_suites(
            organization_id=organization_id, limit=limit, offset=offset
        )

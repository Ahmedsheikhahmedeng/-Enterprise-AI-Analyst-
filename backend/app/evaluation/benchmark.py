"""Benchmark runner executing evaluation suites against AIAnalystService."""

import subprocess
import time
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.service import AIAnalystService
from app.evaluation.config import EvaluationConfig, get_evaluation_config
from app.evaluation.exceptions import (
    EvaluationDatasetNotFoundError,
)
from app.evaluation.scorers.deterministic import DeterministicScorer
from app.models.evaluation import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationDataset,
    EvaluationRun,
)


def get_git_commit() -> str:
    """Retrieve current git HEAD commit hash or 'unknown'."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()[:16]
    except Exception:
        return "unknown"


class BenchmarkRunner:
    """Orchestrates test case execution through the unified AIAnalystService."""

    def __init__(
        self,
        config: EvaluationConfig | None = None,
        scorer: DeterministicScorer | None = None,
    ) -> None:
        self.config = config or get_evaluation_config()
        self.scorer = scorer or DeterministicScorer(self.config)

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
        """Execute benchmark evaluation run synchronously across targeted dataset cases."""
        dataset = await session.get(EvaluationDataset, dataset_id)
        if not dataset:
            raise EvaluationDatasetNotFoundError(
                message=f"Dataset '{dataset_id}' not found for evaluation run.",
                details={"dataset_id": str(dataset_id)},
            )

        target_version = dataset_version or dataset.version

        # 1. Fetch enabled cases for this dataset
        stmt = select(EvaluationCase).where(
            EvaluationCase.dataset_id == dataset_id,
            EvaluationCase.enabled.is_(True),
        )
        if tags:
            # Filter cases that contain any of the given tags
            stmt = stmt.where(EvaluationCase.tags.overlap(tags))

        limit_val = max_cases or self.config.default_max_cases_per_run
        stmt = stmt.order_by(EvaluationCase.created_at.asc()).limit(limit_val)

        cases = list((await session.execute(stmt)).scalars().all())

        # Extract case attributes into detached dictionaries before committing to avoid attribute expiration
        extracted_cases: list[dict[str, Any]] = [
            {
                "id": c.id,
                "query": c.query,
                "datasource_id": c.datasource_id,
                "route_expected": c.route_expected,
                "expected_answer": c.expected_answer,
                "expected_citations": list(c.expected_citations or []),
                "expected_documents": list(c.expected_documents or []),
                "expected_metrics": dict(c.expected_metrics or {}),
                "expected_rows": list(c.expected_rows or []),
                "relevant_chunks": list(c.relevant_chunks or []),
            }
            for c in cases
        ]

        now = datetime.now(UTC)
        run_id = uuid.uuid4()
        run_record = EvaluationRun(
            id=run_id,
            organization_id=organization_id,
            dataset_id=dataset_id,
            dataset_version=target_version,
            status="running",
            started_at=now,
            total_cases=len(extracted_cases),
            passed_cases=0,
            failed_cases=0,
            model_config_={
                "provider": "deterministic",
                "timeout": self.config.case_timeout_seconds,
            },
            system_version="1.0.0",
            git_commit=get_git_commit(),
            duration_ms=0.0,
            created_by=user_id,
            created_at=now,
        )
        session.add(run_record)
        await session.commit()

        t0_total = time.perf_counter()
        case_results: list[EvaluationCaseResult] = []
        passed_count = 0
        failed_count = 0

        for c_data in extracted_cases:
            t0_case = time.perf_counter()
            actual_route: str | None = None
            actual_answer: str = ""
            actual_metrics: dict[str, Any] = {}
            actual_sql: str | None = None
            evidence_items: list[dict[str, Any]] = []
            exec_error: str | None = None
            exec_success = True
            estimated_cost = 0.0
            input_tokens = 0
            output_tokens = 0

            try:
                # Execute query through production AIAnalystService
                res = await analyst_service.ask(
                    query=c_data["query"],
                    organization_id=organization_id,
                    session=session,
                    user_id=user_id,
                    datasource_id=c_data["datasource_id"],
                )
                actual_route = res.route.value if hasattr(res.route, "value") else str(res.route)
                actual_answer = res.answer
                evidence_items = [
                    {
                        "evidence_id": ev.evidence_id,
                        "content": ev.text,
                        "metadata": ev.metadata,
                        "is_calculated": ev.is_calculated,
                    }
                    for ev in res.evidence
                ]
                estimated_cost = res.diagnostics.total_cost_usd
                # Collect SQL and metrics if available in evidence metadata
                for ev in res.evidence:
                    if ev.source_type == "sql" and "metrics" in ev.metadata:
                        actual_metrics.update(ev.metadata["metrics"])

            except Exception as exc:
                exec_success = False
                exec_error = str(exc)
                actual_answer = f"Execution failed: {exc}"

            case_duration_ms = (time.perf_counter() - t0_case) * 1000

            # Score case
            scoring = self.scorer.score_case(
                route_expected=c_data["route_expected"],
                actual_route=actual_route,
                query=c_data["query"],
                actual_answer=actual_answer,
                expected_answer=c_data["expected_answer"],
                expected_citations=c_data["expected_citations"],
                expected_documents=c_data["expected_documents"],
                expected_metrics=c_data["expected_metrics"],
                actual_metrics=actual_metrics,
                evidence_items=evidence_items,
                actual_sql=actual_sql,
                execution_success=exec_success,
                execution_error=exec_error,
            )

            is_passed = scoring["passed"]
            if is_passed:
                passed_count += 1
            else:
                failed_count += 1

            result_rec = EvaluationCaseResult(
                id=uuid.uuid4(),
                run_id=run_id,
                case_id=c_data["id"],
                organization_id=organization_id,
                actual_route=actual_route,
                expected_route=c_data["route_expected"],
                actual_answer=actual_answer,
                expected_answer=c_data["expected_answer"],
                retrieval_score=scoring["retrieval_score"],
                rag_score=scoring["rag_score"],
                sql_score=scoring["sql_score"],
                grounding_score=scoring["grounding_score"],
                citation_score=scoring["citation_score"],
                hallucination_score=scoring["hallucination_score"],
                latency_ms=case_duration_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost=estimated_cost,
                passed=is_passed,
                failure_reason=scoring["failure_reason"],
                trace_id=f"eval-{run_id.hex[:6]}-{c_data['id'].hex[:6]}",
                metrics_detail=scoring["details"],
                created_at=datetime.now(UTC),
            )
            session.add(result_rec)
            case_results.append(result_rec)

        total_duration_ms = (time.perf_counter() - t0_total) * 1000

        # Update run summary
        fresh_run = await session.get(EvaluationRun, run_id)
        if fresh_run:
            fresh_run.status = "completed"
            fresh_run.completed_at = datetime.now(UTC)
            fresh_run.passed_cases = passed_count
            fresh_run.failed_cases = failed_count
            fresh_run.duration_ms = total_duration_ms
            await session.commit()
            await session.refresh(fresh_run)
            return fresh_run, case_results

        return run_record, case_results

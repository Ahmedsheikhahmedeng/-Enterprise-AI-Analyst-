"""Asynchronous concurrent branch executor with shared deadline and partial failure handling."""

import asyncio
import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.config import AnalystConfig, get_analyst_config
from app.analyst.exceptions import AnalystTimeoutError
from app.analyst.models import (
    AnalystBranchResult,
    BranchType,
    ExecutionBranch,
    ExecutionPlan,
)
from app.core.logging import get_logger
from app.rag.service import RAGService
from app.sql_agent.service import SQLAgentService

logger = get_logger("analyst.executor")


class ParallelAnalystExecutor:
    """Executes SQL and RAG branches concurrently within a bounded shared timeout."""

    def __init__(
        self,
        sql_service: SQLAgentService | None = None,
        rag_service: RAGService | None = None,
        config: AnalystConfig | None = None,
    ) -> None:
        self.sql_service = sql_service
        self.rag_service = rag_service
        self.config = config or get_analyst_config()

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        organization_id: UUID,
        *,
        session: AsyncSession,
        user_id: UUID | None = None,
        analysis_run_id: UUID | None = None,
        semantic_plan: Any | None = None,
        graph_paths: list[dict[str, Any]] | None = None,
    ) -> list[AnalystBranchResult]:
        """Execute all branches defined in the plan with concurrency and shared deadline."""
        if not plan.branches:
            return []

        coros = [
            self._execute_single_branch(
                branch=branch,
                organization_id=organization_id,
                session=session,
                user_id=user_id,
                analysis_run_id=analysis_run_id,
                semantic_plan=semantic_plan,
                graph_paths=graph_paths,
            )
            for branch in plan.branches
        ]

        try:
            async with asyncio.timeout(self.config.total_timeout_seconds):
                results = await asyncio.gather(*coros, return_exceptions=True)
        except TimeoutError as exc:
            logger.error(
                "Global analyst request deadline exceeded: %s s",
                self.config.total_timeout_seconds,
            )
            raise AnalystTimeoutError(
                message=f"Global analyst execution exceeded {self.config.total_timeout_seconds}s",
                details={"timeout_seconds": self.config.total_timeout_seconds},
            ) from exc

        branch_results: list[AnalystBranchResult] = []
        for branch, res in zip(plan.branches, results, strict=False):
            if isinstance(res, BaseException):
                logger.warning("Branch %s failed with exception: %s", branch.branch_id, res)
                branch_results.append(
                    AnalystBranchResult(
                        branch_id=branch.branch_id,
                        branch_type=branch.branch_type,
                        success=False,
                        error=str(res),
                    )
                )
            elif isinstance(res, AnalystBranchResult):
                branch_results.append(res)

        return branch_results

    async def _execute_single_branch(
        self,
        branch: ExecutionBranch,
        organization_id: UUID,
        session: AsyncSession,
        user_id: UUID | None,
        analysis_run_id: UUID | None,
        semantic_plan: Any | None = None,
        graph_paths: list[dict[str, Any]] | None = None,
    ) -> AnalystBranchResult:
        """Execute a single SQL or RAG branch with branch-level timeout."""
        t0 = time.perf_counter()

        try:
            async with asyncio.timeout(branch.timeout_seconds):
                if branch.branch_type == BranchType.SQL:
                    if not branch.datasource_id:
                        msg = f"Branch {branch.branch_id} missing required datasource_id."
                        raise ValueError(msg)
                    if self.sql_service is None:
                        msg = "SQL service is not configured or unavailable."
                        raise RuntimeError(msg)

                    sql_res = await self.sql_service.execute_question(
                        question=branch.query,
                        datasource_id=branch.datasource_id,
                        organization_id=organization_id,
                        session=session,
                        user_id=user_id,
                        limit=branch.limit,
                        analyze=True,
                        analysis_run_id=analysis_run_id,
                        semantic_plan=semantic_plan,
                        graph_paths=graph_paths,
                    )
                    latency = (time.perf_counter() - t0) * 1000
                    return AnalystBranchResult(
                        branch_id=branch.branch_id,
                        branch_type=BranchType.SQL,
                        success=True,
                        data=sql_res,
                        latency_ms=latency,
                    )

                elif branch.branch_type == BranchType.RAG:
                    if self.rag_service is None:
                        msg = "RAG service is not configured or unavailable."
                        raise RuntimeError(msg)

                    rag_res = await self.rag_service.answer(
                        query=branch.query,
                        organization_id=organization_id,
                        session=session,
                        top_k=branch.top_k,
                        user_id=user_id,
                        analysis_run_id=analysis_run_id,
                    )
                    latency = (time.perf_counter() - t0) * 1000
                    return AnalystBranchResult(
                        branch_id=branch.branch_id,
                        branch_type=BranchType.RAG,
                        success=True,
                        data=rag_res,
                        latency_ms=latency,
                    )
                else:
                    raise ValueError(f"Unknown branch type {branch.branch_type}")

        except TimeoutError:
            latency = (time.perf_counter() - t0) * 1000
            logger.warning(
                "Branch %s timed out after %s s", branch.branch_id, branch.timeout_seconds
            )
            return AnalystBranchResult(
                branch_id=branch.branch_id,
                branch_type=branch.branch_type,
                success=False,
                error=f"Branch timed out after {branch.timeout_seconds}s",
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.perf_counter() - t0) * 1000
            logger.exception("Branch %s execution failed: %s", branch.branch_id, exc)
            return AnalystBranchResult(
                branch_id=branch.branch_id,
                branch_type=branch.branch_type,
                success=False,
                error=str(exc),
                latency_ms=latency,
            )

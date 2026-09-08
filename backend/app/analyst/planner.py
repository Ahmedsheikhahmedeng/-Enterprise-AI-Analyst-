"""Deterministic execution planner for the Unified AI Analyst."""

import uuid
from uuid import UUID

from app.analyst.config import AnalystConfig, get_analyst_config
from app.analyst.exceptions import AnalystBudgetExceededError
from app.analyst.models import (
    AnalystRouteType,
    BranchType,
    ExecutionBranch,
    ExecutionPlan,
)
from app.analyst.router import AnalystQueryRouter


class DeterministicAnalystPlanner:
    """Builds explicit, bounded execution plans across SQL and RAG branches."""

    def __init__(
        self,
        router: AnalystQueryRouter | None = None,
        config: AnalystConfig | None = None,
    ) -> None:
        self.router = router or AnalystQueryRouter()
        self.config = config or get_analyst_config()

    def plan(
        self,
        query: str,
        datasource_id: UUID | None = None,
        *,
        limit: int | None = None,
        top_k: int | None = None,
    ) -> ExecutionPlan:
        """Analyze query intent and assemble concrete, deduplicated execution branches."""
        classification = self.router.classify(query=query, datasource_id=datasource_id)
        plan_id = uuid.uuid4()
        branches: list[ExecutionBranch] = []

        eff_limit = limit or 1000
        eff_top_k = top_k or 10

        if classification.route == AnalystRouteType.SQL:
            if datasource_id:
                branches.append(
                    ExecutionBranch(
                        branch_id="b_sql_1",
                        branch_type=BranchType.SQL,
                        query=classification.structured_subquery or query,
                        datasource_id=datasource_id,
                        limit=eff_limit,
                        timeout_seconds=self.config.sql_timeout_seconds,
                    )
                )
        elif classification.route == AnalystRouteType.RAG:
            branches.append(
                ExecutionBranch(
                    branch_id="b_rag_1",
                    branch_type=BranchType.RAG,
                    query=classification.unstructured_subquery or query,
                    top_k=eff_top_k,
                    timeout_seconds=self.config.rag_timeout_seconds,
                )
            )
        elif classification.route == AnalystRouteType.HYBRID:
            # Construct both SQL and RAG branches
            if datasource_id:
                branches.append(
                    ExecutionBranch(
                        branch_id="b_sql_1",
                        branch_type=BranchType.SQL,
                        query=classification.structured_subquery or query,
                        datasource_id=datasource_id,
                        limit=eff_limit,
                        timeout_seconds=self.config.sql_timeout_seconds,
                    )
                )
            branches.append(
                ExecutionBranch(
                    branch_id="b_rag_1",
                    branch_type=BranchType.RAG,
                    query=classification.unstructured_subquery or query,
                    top_k=eff_top_k,
                    timeout_seconds=self.config.rag_timeout_seconds,
                )
            )

        # Deduplicate branches by (branch_type, query, datasource_id)
        seen: set[tuple[str, str, UUID | None]] = set()
        deduped_branches: list[ExecutionBranch] = []
        for b in branches:
            key = (b.branch_type.value, b.query.strip().lower(), b.datasource_id)
            if key not in seen:
                seen.add(key)
                deduped_branches.append(b)

        # Enforce budget
        if len(deduped_branches) > self.config.max_branches:
            msg = (
                f"Plan generated {len(deduped_branches)} branches, "
                f"exceeding max {self.config.max_branches}."
            )
            raise AnalystBudgetExceededError(
                message=msg,
                details={
                    "max_branches": self.config.max_branches,
                    "branches": len(deduped_branches),
                },
            )

        return ExecutionPlan(
            plan_id=plan_id,
            original_query=query,
            route=classification.route,
            confidence=classification.confidence,
            branches=deduped_branches,
            requires_final_generation=True,
            reason=classification.reason,
            budget_max_evidence=self.config.max_evidence,
        )

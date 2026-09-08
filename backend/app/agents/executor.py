"""Step-level tool executor enforcing 8-point security gate and output handling."""

import asyncio
from typing import Any

from app.agents.budgets import AgentBudgetManager
from app.agents.checkpoints import CheckpointManager
from app.agents.context import AgentExecutionContext
from app.agents.exceptions import (
    LoopDetectedError,
    ToolExecutionError,
)
from app.agents.policies import AgentToolPolicy
from app.agents.provenance import EvidenceItem, ProvenanceTracker
from app.agents.registry import ToolRegistry
from app.agents.tools.base import ToolOutput


class LoopDetector:
    """Detects repeated identical tool calls to prevent infinite loops."""

    def __init__(self, threshold: int = 3) -> None:
        self.threshold = threshold
        self._history: list[tuple[str, str]] = []

    def record_and_check(self, tool_name: str, input_hash: str) -> None:
        entry = (tool_name, input_hash)
        self._history.append(entry)
        count = sum(1 for e in self._history if e == entry)
        if count >= self.threshold:
            raise LoopDetectedError(tool_name=tool_name, count=count)


class StepExecutor:
    """Executes an individual agent step through strict pre-flight and post-flight gates."""

    def __init__(
        self,
        registry: ToolRegistry,
        policy: AgentToolPolicy,
        budget_manager: AgentBudgetManager,
        checkpoint_manager: CheckpointManager,
        provenance_tracker: ProvenanceTracker,
        loop_detector: LoopDetector | None = None,
        step_timeout_seconds: float = 60.0,
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.budget_manager = budget_manager
        self.checkpoint_manager = checkpoint_manager
        self.provenance_tracker = provenance_tracker
        self.loop_detector = loop_detector or LoopDetector()
        self.step_timeout_seconds = step_timeout_seconds

    async def execute_step(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: AgentExecutionContext,
        user_permissions: set[str],
        requires_approval: bool = False,
    ) -> ToolOutput:
        """Execute step through 8-point pre-flight security gate and post-flight evidence capture."""
        # 1. Tool existence check
        tool = self.registry.get(tool_name)

        # 2. Input hash & loop detection
        input_hash = CheckpointManager.compute_input_hash(tool_input)
        self.loop_detector.record_and_check(tool_name, input_hash)

        # 3. Duplicate idempotent call check (replay avoidance)
        if tool.idempotent:
            existing_cp = await self.checkpoint_manager.find_matching_checkpoint(
                db_session=context.db_session,
                session_id=context.session_id,
                tool_name=tool_name,
                tool_input=tool_input,
            )
            if existing_cp and existing_cp.state_snapshot:
                # Return cached output without re-executing
                cached_data = existing_cp.state_snapshot.get("data", {})
                for ev_id in existing_cp.evidence_ids:
                    self.provenance_tracker.record_evidence(
                        EvidenceItem(
                            evidence_id=ev_id,
                            source_type=tool_name.split(".")[0],
                            content=f"Reused evidence from checkpoint {existing_cp.id}",
                        )
                    )
                self.provenance_tracker.record_tool(tool_name)
                return ToolOutput(
                    success=True,
                    data=cached_data,
                    tokens_used=0,
                    cost_usd=0.0,
                    duration_ms=0.0,
                )

        # 4. Tool Authorization (Tenant, RBAC, Profile Allowlist, Risk Tier)
        self.policy.authorize_tool(
            tool_name=tool.name,
            tool_risk_level=tool.risk_level,
            required_permission=tool.required_permission,
            user_permissions=user_permissions,
            organization_id=context.organization_id,
        )

        # 5. Schema Validation
        validated_input = await tool.validate(tool_input)

        # 6. Budget Pre-flight check
        self.budget_manager.pre_flight_check()

        # 7. Step execution with timeout
        try:
            output = await asyncio.wait_for(
                tool.execute(validated_input, context),
                timeout=self.step_timeout_seconds,
            )
        except TimeoutError as exc:
            raise ToolExecutionError(
                tool_name, f"Step execution timed out after {self.step_timeout_seconds}s"
            ) from exc
        except Exception as exc:
            raise ToolExecutionError(tool_name, str(exc)) from exc

        # 8. Post-flight updates: consume budgets and record provenance
        self.budget_manager.step_budget.consume_step()
        self.budget_manager.step_budget.consume_tool_call()
        self.budget_manager.token_budget.consume(output.tokens_used)
        self.budget_manager.cost_budget.consume(output.cost_usd)

        for ev in output.evidence_items:
            self.provenance_tracker.record_evidence(
                EvidenceItem(
                    evidence_id=ev.get("evidence_id", "EV-0"),
                    source_type=ev.get("source_type", tool_name.split(".")[0]),
                    content=ev.get("content", ""),
                    metadata=ev.get("metadata", {}),
                )
            )
        self.provenance_tracker.record_tool(tool_name)

        return output

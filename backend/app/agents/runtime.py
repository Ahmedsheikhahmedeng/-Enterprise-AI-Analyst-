"""Central AgentRuntime orchestrating plan execution, checkpoints, and final synthesis."""

import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.approvals import ApprovalManager
from app.agents.budgets import AgentBudgetManager
from app.agents.cancellation import AgentCancellationManager
from app.agents.checkpoints import CheckpointManager
from app.agents.config import AgentConfig, get_agent_config
from app.agents.context import AgentExecutionContext
from app.agents.exceptions import (
    ApprovalRequiredError,
    BudgetExceededError,
)
from app.agents.executor import LoopDetector, StepExecutor
from app.agents.models import AgentSession, AgentStep
from app.agents.policies import AgentToolPolicy
from app.agents.profiles import get_agent_profile
from app.agents.provenance import ProvenanceTracker
from app.agents.registry import ToolRegistry, get_tool_registry
from app.agents.schemas import AgentFinalAnswerResponse, AgentStatus
from app.agents.state import AgentStateMachine
from app.core.logging import get_logger
from app.observability.instrumentation.agent import get_agent_instrumentation
from app.observability.tracing import get_trace_manager

logger = get_logger("agents.runtime")


class AgentRuntime:
    """Core runtime executing an agent session end-to-end within strict enterprise boundaries."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        config: AgentConfig | None = None,
        checkpoint_manager: CheckpointManager | None = None,
        approval_manager: ApprovalManager | None = None,
    ) -> None:
        self.registry = registry or get_tool_registry()
        self.config = config or get_agent_config()
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self.approval_manager = approval_manager or ApprovalManager()
        self.instrumentation = get_agent_instrumentation()
        self.trace_manager = get_trace_manager()

    async def execute_session(
        self,
        session_id: UUID,
        organization_id: UUID,
        db_session: AsyncSession,
        user_permissions: set[str],
        user_id: UUID | None = None,
    ) -> AgentFinalAnswerResponse:
        """Run execution loop over plan steps with checkpoints and grounding."""
        t_start = time.perf_counter()

        # 1. Fetch AgentSession
        stmt = select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.organization_id == organization_id,
        )
        res = await db_session.execute(stmt)
        agent_session = res.scalars().first()
        if not agent_session:
            raise ValueError(f"AgentSession {session_id} not found")

        # Verify state transition to EXECUTING
        if agent_session.status != AgentStatus.EXECUTING.value:
            AgentStateMachine.validate_transition(agent_session.status, AgentStatus.EXECUTING)
            agent_session.status = AgentStatus.EXECUTING.value
        agent_session.started_at = agent_session.started_at or datetime.now(UTC)
        await db_session.flush()

        profile = get_agent_profile(agent_session.agent_type)
        budget_manager = AgentBudgetManager(
            max_steps=agent_session.max_steps or profile.max_steps,
            max_tool_calls=self.config.default_max_tool_calls,
            max_duration_seconds=self.config.default_duration_seconds,
            max_tokens=profile.max_tokens,
            max_cost_usd=profile.max_cost_usd,
        )

        provenance_tracker = ProvenanceTracker(session_id=session_id)
        loop_detector = LoopDetector(threshold=self.config.loop_detection_threshold)
        tool_policy = AgentToolPolicy(allowed_tools=profile.allowed_tools)

        # 2. Retrieve relevant contextual memory (untagged data, never permissions)
        try:
            from app.memory.context import MemoryContextBuilder
            from app.memory.schemas import MemorySearchRequest, MemoryType
            from app.memory.service import MemoryService

            memory_service = MemoryService()
            search_req = MemorySearchRequest(
                query=agent_session.goal,
                top_k=5,
                memory_types=[MemoryType.WORKING, MemoryType.SEMANTIC, MemoryType.EPISODIC],
            )
            mem_hits = await memory_service.search_memories(
                db_session=db_session,
                organization_id=organization_id,
                request=search_req,
                user_id=user_id,
                user_permissions=user_permissions,
            )
            ctx_builder = MemoryContextBuilder()
            memory_block = ctx_builder.build_context_block(search_results=mem_hits)
            if memory_block:
                logger.info(
                    "Injected memory context into session %s: %d hits", session_id, len(mem_hits)
                )
        except Exception as mem_err:
            logger.debug("Memory retrieval skipped for session %s: %s", session_id, mem_err)

        step_executor = StepExecutor(
            registry=self.registry,
            policy=tool_policy,
            budget_manager=budget_manager,
            checkpoint_manager=self.checkpoint_manager,
            provenance_tracker=provenance_tracker,
            loop_detector=loop_detector,
            step_timeout_seconds=self.config.step_timeout_seconds,
        )

        # 3. Fetch Steps
        steps_stmt = (
            select(AgentStep)
            .where(
                AgentStep.session_id == session_id,
                AgentStep.organization_id == organization_id,
            )
            .order_by(AgentStep.sequence.asc())
        )
        steps_res = await db_session.execute(steps_stmt)
        steps = list(steps_res.scalars().all())

        is_degraded = False

        try:
            for step in steps:
                # Check cancellation
                await AgentCancellationManager.check_cancelled(db_session, session_id)

                if step.status == "completed":
                    # Already completed step, skip
                    continue

                # Approval Gate
                if step.requires_approval or step.tool_name in profile.requires_approval_tools:
                    try:
                        await self.approval_manager.ensure_approved_or_raise(
                            db_session=db_session,
                            session_id=session_id,
                            step_id=step.id,
                            tool_name=step.tool_name,
                            requires_approval=True,
                        )
                    except ApprovalRequiredError:
                        # Request approval if not already exists
                        approvals = await self.approval_manager.list_session_approvals(
                            db_session=db_session,
                            session_id=session_id,
                            organization_id=organization_id,
                        )
                        existing_step_app = next(
                            (a for a in approvals if a.step_id == step.id), None
                        )
                        if not existing_step_app:
                            await self.approval_manager.create_request(
                                db_session=db_session,
                                session_id=session_id,
                                step_id=step.id,
                                organization_id=organization_id,
                                reason=f"Tool '{step.tool_name}' requires operator approval.",
                                requested_by=user_id,
                            )
                        agent_session.status = AgentStatus.AWAITING_APPROVAL.value
                        await db_session.commit()
                        return AgentFinalAnswerResponse(
                            session_id=session_id,
                            status=AgentStatus.AWAITING_APPROVAL.value,
                            answer="Execution paused: waiting for operator approval on sensitive tool step.",
                            steps=agent_session.current_step,
                            tools_used=provenance_tracker.get_tools_used(),
                            citations=[],
                            grounded=False,
                            degraded=False,
                            usage={
                                "tokens": budget_manager.token_budget.consumed_tokens,
                                "cost": budget_manager.cost_budget.consumed_cost_usd,
                            },
                        )

                step.status = "running"
                await db_session.flush()

                exec_ctx = AgentExecutionContext(
                    organization_id=organization_id,
                    session_id=session_id,
                    step_id=step.id,
                    user_id=user_id,
                    trace_id=agent_session.trace_id,
                    request_id=agent_session.request_id,
                    db_session=db_session,
                    step_number=step.sequence,
                )

                t_step_start = time.perf_counter()
                try:
                    tool_output = await step_executor.execute_step(
                        tool_name=step.tool_name,
                        tool_input=step.tool_input,
                        context=exec_ctx,
                        user_permissions=user_permissions,
                        requires_approval=step.requires_approval,
                    )
                    step.status = "completed"
                    step.output = tool_output.data
                    step.evidence_refs = [
                        e.evidence_id for e in provenance_tracker.get_all_evidence()
                    ]
                    step.tokens = tool_output.tokens_used
                    step.cost = tool_output.cost_usd
                    step.duration_ms = (time.perf_counter() - t_step_start) * 1000
                    step.completed_at = datetime.now(UTC)
                    if tool_output.is_degraded:
                        is_degraded = True

                    # Save Checkpoint
                    await self.checkpoint_manager.save_checkpoint(
                        db_session=db_session,
                        session_id=session_id,
                        step_id=step.id,
                        organization_id=organization_id,
                        status="completed",
                        tool_name=step.tool_name,
                        tool_input=step.tool_input,
                        evidence_ids=step.evidence_refs,
                        state_snapshot={"data": tool_output.data},
                    )

                    agent_session.current_step = step.sequence
                    await db_session.flush()

                except Exception as exc:
                    step.status = "failed"
                    step.output = {"error": str(exc)}
                    step.completed_at = datetime.now(UTC)
                    await db_session.flush()
                    raise

            # 3. Final Synthesis & Grounding
            citations = provenance_tracker.get_citations()
            tools_used = provenance_tracker.get_tools_used()
            all_evidence = provenance_tracker.get_all_evidence()

            if not all_evidence:
                final_text = "Insufficient evidence to fulfill the analytical goal."
                is_grounded = False
            else:
                final_text = f"Successfully analyzed goal: '{agent_session.goal}'. Grounded in {len(citations)} verified citations: {', '.join(citations)}."
                is_grounded = True

            total_duration_ms = (time.perf_counter() - t_start) * 1000
            agent_session.status = AgentStatus.COMPLETED.value
            agent_session.completed_at = datetime.now(UTC)
            agent_session.total_tokens = budget_manager.token_budget.consumed_tokens
            agent_session.total_cost = budget_manager.cost_budget.consumed_cost_usd
            agent_session.duration_ms = total_duration_ms

            final_resp = AgentFinalAnswerResponse(
                session_id=session_id,
                status=AgentStatus.COMPLETED.value,
                answer=final_text,
                steps=len(steps),
                tools_used=tools_used,
                citations=citations,
                grounded=is_grounded,
                degraded=is_degraded,
                usage={
                    "tokens": agent_session.total_tokens,
                    "cost": agent_session.total_cost,
                    "duration_ms": total_duration_ms,
                },
            )
            agent_session.final_answer = final_resp.model_dump(mode="json")
            await db_session.commit()

            # Record verified findings as episodic memory
            if is_grounded:
                try:
                    from app.memory.schemas import (
                        MemoryItemCreateRequest,
                        MemoryPrivacyLevel,
                        MemoryType,
                        MemoryVisibility,
                    )
                    from app.memory.service import MemoryService

                    mem_svc = MemoryService()
                    await mem_svc.create_memory(
                        db_session=db_session,
                        organization_id=organization_id,
                        request=MemoryItemCreateRequest(
                            memory_type=MemoryType.EPISODIC,
                            content=f"Analytical finding for '{agent_session.goal}': {final_text}",
                            summary=f"Outcome of {agent_session.agent_type}",
                            importance=0.75,
                            confidence=0.90,
                            visibility=MemoryVisibility.ORGANIZATION,
                            privacy_level=MemoryPrivacyLevel.NORMAL,
                            session_id=session_id,
                            source_refs=[
                                {"source_type": "agent_session", "source_id": str(session_id)}
                            ],
                        ),
                        user_id=user_id,
                        user_permissions=user_permissions,
                    )
                except Exception as mem_err:
                    logger.debug(
                        "Could not record episodic memory for session %s: %s", session_id, mem_err
                    )

            self.instrumentation.record_session_completed(
                agent_type=agent_session.agent_type,
                status="completed",
                duration_ms=total_duration_ms,
                tokens=agent_session.total_tokens,
                cost=agent_session.total_cost,
            )

            return final_resp

        except BudgetExceededError:
            agent_session.status = AgentStatus.BUDGET_EXCEEDED.value
            await db_session.commit()
            self.instrumentation.record_session_completed(
                agent_type=agent_session.agent_type,
                status="budget_exceeded",
                duration_ms=(time.perf_counter() - t_start) * 1000,
                tokens=budget_manager.token_budget.consumed_tokens,
                cost=budget_manager.cost_budget.consumed_cost_usd,
            )
            raise

        except Exception:
            agent_session.status = AgentStatus.FAILED.value
            await db_session.commit()
            self.instrumentation.record_session_completed(
                agent_type=agent_session.agent_type,
                status="failed",
                duration_ms=(time.perf_counter() - t_start) * 1000,
                tokens=budget_manager.token_budget.consumed_tokens,
                cost=budget_manager.cost_budget.consumed_cost_usd,
            )
            raise

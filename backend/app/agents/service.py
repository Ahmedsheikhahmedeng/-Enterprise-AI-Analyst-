"""Application service coordinating session creation, planning, resumption, cancellation, and approvals."""

import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.approvals import ApprovalManager
from app.agents.checkpoints import CheckpointManager
from app.agents.config import AgentConfig, get_agent_config
from app.agents.exceptions import AgentSessionNotFoundError, ToolAuthorizationError
from app.agents.models import AgentPlan, AgentSession, AgentStep
from app.agents.plan import AgentPlanValidator
from app.agents.profiles import get_agent_profile
from app.agents.providers.deterministic import DeterministicAgentPlanner
from app.agents.registry import get_tool_registry
from app.agents.runtime import AgentRuntime
from app.agents.schemas import (
    AgentFinalAnswerResponse,
    AgentSessionCreateRequest,
    AgentStatus,
)
from app.agents.state import AgentStateMachine
from app.models.audit import AuditLog
from app.observability.instrumentation.agent import get_agent_instrumentation


class AgentService:
    """Service handling high-level agent sessions, audits, persistence, and transitions."""

    def __init__(
        self,
        config: AgentConfig | None = None,
        runtime: AgentRuntime | None = None,
        approval_manager: ApprovalManager | None = None,
        checkpoint_manager: CheckpointManager | None = None,
    ) -> None:
        self.config = config or get_agent_config()
        self.runtime = runtime or AgentRuntime(config=self.config)
        self.approval_manager = approval_manager or ApprovalManager()
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self.planner = DeterministicAgentPlanner()
        self.instrumentation = get_agent_instrumentation()

    async def create_session(
        self,
        db_session: AsyncSession,
        organization_id: UUID,
        req: AgentSessionCreateRequest,
        user_id: UUID | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> tuple[AgentSession, AgentPlan]:
        """Create new AgentSession and generate its initial structured plan."""
        profile = get_agent_profile(req.agent_type)
        session_id = uuid.uuid4()
        max_steps = req.max_steps or profile.max_steps

        # 1. Generate plan steps
        plan_steps = await self.planner.generate_plan(
            goal=req.goal,
            agent_type=req.agent_type,
            datasource_id=req.datasource_id,
            max_steps=max_steps,
        )

        # 2. Validate plan
        validator = AgentPlanValidator(
            registered_tools=get_tool_registry().tool_names(),
            max_steps=max_steps,
            max_tokens=req.max_tokens or profile.max_tokens,
            max_cost_usd=req.max_cost_usd or profile.max_cost_usd,
        )
        total_est_cost = sum(s.estimated_cost for s in plan_steps)
        validator.validate(steps=plan_steps, estimated_cost=total_est_cost)

        # 3. Create Session Record
        agent_session = AgentSession(
            id=session_id,
            organization_id=organization_id,
            created_by=user_id,
            status=AgentStatus.CREATED.value,
            agent_type=req.agent_type.value,
            goal=req.goal,
            max_steps=max_steps,
            trace_id=trace_id,
            request_id=request_id,
        )
        db_session.add(agent_session)
        await db_session.flush()

        # 4. Create Plan Record
        plan_id = uuid.uuid4()
        requires_approval = any(s.requires_approval for s in plan_steps)
        plan = AgentPlan(
            id=plan_id,
            session_id=session_id,
            organization_id=organization_id,
            goal=req.goal,
            steps=[s.model_dump() for s in plan_steps],
            estimated_cost=total_est_cost,
            estimated_tokens=sum(
                s.estimated_duration * 100 for s in plan_steps
            ),  # rough token estimate
            estimated_duration=sum(s.estimated_duration for s in plan_steps),
            requires_approval=requires_approval,
        )
        db_session.add(plan)
        agent_session.plan_id = plan_id
        agent_session.status = AgentStatus.PLANNED.value
        await db_session.flush()

        # 5. Materialize Steps
        for s in plan_steps:
            step_record = AgentStep(
                id=uuid.UUID(s.step_id),
                session_id=session_id,
                plan_id=plan_id,
                organization_id=organization_id,
                sequence=s.sequence,
                tool_name=s.tool_name,
                tool_input=s.tool_input,
                reason=s.reason,
                status="pending",
                requires_approval=s.requires_approval,
            )
            db_session.add(step_record)

        # Audit log
        db_session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="agent.session_created",
                resource_type="agent_session",
                resource_id=str(session_id),
                metadata_={"agent_type": req.agent_type.value, "goal": req.goal[:100]},
            )
        )
        await db_session.commit()

        self.instrumentation.record_session_started(req.agent_type.value)
        return agent_session, plan

    async def get_session(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        organization_id: UUID,
    ) -> AgentSession:
        """Retrieve agent session by ID within tenant boundary."""
        stmt = select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.organization_id == organization_id,
        )
        res = await db_session.execute(stmt)
        sess = res.scalars().first()
        if not sess:
            raise AgentSessionNotFoundError(session_id)
        return sess

    async def get_session_plan(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        organization_id: UUID,
    ) -> AgentPlan | None:
        """Retrieve execution plan for an agent session."""
        stmt = select(AgentPlan).where(
            AgentPlan.session_id == session_id,
            AgentPlan.organization_id == organization_id,
        )
        res = await db_session.execute(stmt)
        return res.scalars().first()

    async def get_session_steps(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        organization_id: UUID,
    ) -> list[AgentStep]:
        """Retrieve steps for an agent session."""
        stmt = (
            select(AgentStep)
            .where(
                AgentStep.session_id == session_id,
                AgentStep.organization_id == organization_id,
            )
            .order_by(AgentStep.sequence.asc())
        )
        res = await db_session.execute(stmt)
        return list(res.scalars().all())

    async def start_session(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        organization_id: UUID,
        user_permissions: set[str],
        user_id: UUID | None = None,
    ) -> AgentFinalAnswerResponse:
        from app.rbac.catalog import PERM_AGENTS_EXECUTE

        if PERM_AGENTS_EXECUTE not in user_permissions:
            raise ToolAuthorizationError(
                tool_name="session.start",
                reason="User lacks permission to execute agent session",
            )

        # Validate session existence within tenant boundary
        await self.get_session(db_session, session_id, organization_id)
        return await self.runtime.execute_session(
            session_id=session_id,
            organization_id=organization_id,
            db_session=db_session,
            user_permissions=user_permissions,
            user_id=user_id,
        )

    async def cancel_session(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        organization_id: UUID,
        user_id: UUID | None = None,
    ) -> AgentSession:
        """Cancel an active or pending agent session."""
        sess = await self.get_session(db_session, session_id, organization_id)
        AgentStateMachine.validate_transition(sess.status, AgentStatus.CANCELLED)
        sess.status = AgentStatus.CANCELLED.value
        sess.cancelled_at = datetime.now(UTC)

        db_session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="agent.session_cancelled",
                resource_type="agent_session",
                resource_id=str(session_id),
            )
        )
        await db_session.commit()
        return sess

    async def resume_session(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        organization_id: UUID,
        user_permissions: set[str],
        user_id: UUID | None = None,
    ) -> AgentFinalAnswerResponse:
        """Resume execution of a paused or awaiting_approval session."""
        from app.rbac.catalog import PERM_AGENTS_EXECUTE, PERM_AGENTS_RESUME

        if not (PERM_AGENTS_RESUME in user_permissions or PERM_AGENTS_EXECUTE in user_permissions):
            raise ToolAuthorizationError(
                tool_name="session.resume",
                reason="User lacks permission to resume agent session",
            )

        sess = await self.get_session(db_session, session_id, organization_id)
        if sess.status not in (AgentStatus.PAUSED.value, AgentStatus.AWAITING_APPROVAL.value):
            AgentStateMachine.validate_transition(sess.status, AgentStatus.EXECUTING)

        sess.status = AgentStatus.EXECUTING.value
        await db_session.commit()

        db_session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="agent.session_resumed",
                resource_type="agent_session",
                resource_id=str(session_id),
            )
        )
        await db_session.commit()

        return await self.runtime.execute_session(
            session_id=session_id,
            organization_id=organization_id,
            db_session=db_session,
            user_permissions=user_permissions,
            user_id=user_id,
        )

"""FastAPI Router for Enterprise Agent Runtime."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.approvals import ApprovalManager
from app.agents.exceptions import (
    AgentError,
    AgentSessionNotFoundError,
    AgentStateTransitionError,
    BudgetExceededError,
    LoopDetectedError,
    PlanValidationError,
    ToolAuthorizationError,
    ToolInputValidationError,
)
from app.agents.schemas import (
    AgentFinalAnswerResponse,
    AgentPlanResponse,
    AgentSessionCreateRequest,
    AgentSessionResponse,
    AgentStepResponse,
    ApprovalDecisionRequest,
    ApprovalResponse,
    ApprovalStatus,
)
from app.agents.service import AgentService
from app.auth.dependencies import get_current_user
from app.core.logging import get_logger
from app.db.postgres import get_db_session
from app.models.user import User
from app.rbac.catalog import (
    PERM_AGENTS_APPROVE,
    PERM_AGENTS_CANCEL,
    PERM_AGENTS_CREATE,
    PERM_AGENTS_EXECUTE,
    PERM_AGENTS_READ,
    PERM_AGENTS_RESUME,
)
from app.rbac.dependencies import require_permission
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_tenant_context

logger = get_logger("api.agents")
router = APIRouter(prefix="/agents", tags=["Agents"])


def get_agent_service() -> AgentService:
    return AgentService()


@router.post(
    "/sessions",
    response_model=AgentSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create agent session and initial plan",
)
async def create_agent_session(
    payload: AgentSessionCreateRequest,
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    _perm: Annotated[User, Depends(require_permission(PERM_AGENTS_CREATE))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    x_trace_id: Annotated[str | None, Header()] = None,
    x_request_id: Annotated[str | None, Header()] = None,
) -> AgentSessionResponse:
    """Initialize a new bounded agent session with a validated execution plan."""
    service = get_agent_service()
    try:
        session, _plan = await service.create_session(
            db_session=db_session,
            organization_id=tenant_ctx.organization_id,
            req=payload,
            user_id=current_user.id,
            trace_id=x_trace_id,
            request_id=x_request_id,
        )
        return AgentSessionResponse.model_validate(session)
    except PlanValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
        ) from exc
    except AgentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc


@router.get(
    "/sessions/{session_id}",
    response_model=AgentSessionResponse,
    summary="Get agent session details",
)
async def get_agent_session(
    session_id: UUID,
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    _perm: Annotated[User, Depends(require_permission(PERM_AGENTS_READ))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentSessionResponse:
    """Retrieve an existing agent session within the caller's tenant."""
    service = get_agent_service()
    try:
        session = await service.get_session(db_session, session_id, tenant_ctx.organization_id)
        return AgentSessionResponse.model_validate(session)
    except AgentSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc


@router.get(
    "/sessions/{session_id}/plan",
    response_model=AgentPlanResponse,
    summary="Get agent session execution plan",
)
async def get_agent_session_plan(
    session_id: UUID,
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    _perm: Annotated[User, Depends(require_permission(PERM_AGENTS_READ))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentPlanResponse:
    """Retrieve the generated execution plan for an agent session."""
    service = get_agent_service()
    plan = await service.get_session_plan(db_session, session_id, tenant_ctx.organization_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found for session"
        )
    return AgentPlanResponse.model_validate(plan)


@router.get(
    "/sessions/{session_id}/steps",
    response_model=list[AgentStepResponse],
    summary="Get execution steps for session",
)
async def get_agent_session_steps(
    session_id: UUID,
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    _perm: Annotated[User, Depends(require_permission(PERM_AGENTS_READ))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AgentStepResponse]:
    """Retrieve all materialized execution steps and tool invocation traces for a session."""
    service = get_agent_service()
    steps = await service.get_session_steps(db_session, session_id, tenant_ctx.organization_id)
    return [AgentStepResponse.model_validate(s) for s in steps]


@router.post(
    "/sessions/{session_id}/start",
    response_model=AgentFinalAnswerResponse,
    summary="Start agent session execution",
)
async def start_agent_session(
    session_id: UUID,
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    _perm: Annotated[User, Depends(require_permission(PERM_AGENTS_EXECUTE))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentFinalAnswerResponse:
    """Trigger execution of an agent session through its plan steps."""
    service = get_agent_service()
    user_perms = set(tenant_ctx.permissions or [])
    try:
        return await service.start_session(
            db_session=db_session,
            session_id=session_id,
            organization_id=tenant_ctx.organization_id,
            user_permissions=user_perms,
            user_id=current_user.id,
        )
    except AgentSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except AgentStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except (BudgetExceededError, LoopDetectedError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except (ToolAuthorizationError, ToolInputValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message) from exc


@router.post(
    "/sessions/{session_id}/cancel",
    response_model=AgentSessionResponse,
    summary="Cancel agent session",
)
async def cancel_agent_session(
    session_id: UUID,
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    _perm: Annotated[User, Depends(require_permission(PERM_AGENTS_CANCEL))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentSessionResponse:
    """Explicitly cancel an active or planned agent session."""
    service = get_agent_service()
    try:
        session = await service.cancel_session(
            db_session=db_session,
            session_id=session_id,
            organization_id=tenant_ctx.organization_id,
            user_id=current_user.id,
        )
        return AgentSessionResponse.model_validate(session)
    except AgentSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except AgentStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc


@router.post(
    "/sessions/{session_id}/resume",
    response_model=AgentFinalAnswerResponse,
    summary="Resume paused or checkpointed agent session",
)
async def resume_agent_session(
    session_id: UUID,
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    _perm: Annotated[User, Depends(require_permission(PERM_AGENTS_RESUME))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentFinalAnswerResponse:
    """Resume execution of a paused or awaiting_approval session from its latest checkpoint."""
    service = get_agent_service()
    user_perms = set(tenant_ctx.permissions or [])
    try:
        return await service.resume_session(
            db_session=db_session,
            session_id=session_id,
            organization_id=tenant_ctx.organization_id,
            user_permissions=user_perms,
            user_id=current_user.id,
        )
    except AgentSessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except AgentStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc


# ---------------------------------------------------------------------------
# Approvals Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/sessions/{session_id}/approvals",
    response_model=list[ApprovalResponse],
    summary="List approvals for session",
)
@router.get(
    "/{session_id}/approvals",
    response_model=list[ApprovalResponse],
    summary="List approvals for session (alias)",
    include_in_schema=False,
)
async def list_session_approvals(
    session_id: UUID,
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    _perm: Annotated[User, Depends(require_permission(PERM_AGENTS_READ))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ApprovalResponse]:
    """Retrieve all approval requests associated with an agent session."""
    approval_mgr = ApprovalManager()
    approvals = await approval_mgr.list_session_approvals(
        db_session=db_session,
        session_id=session_id,
        organization_id=tenant_ctx.organization_id,
    )
    return [ApprovalResponse.model_validate(a) for a in approvals]


@router.post(
    "/sessions/{session_id}/approvals/{approval_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve sensitive tool execution",
)
@router.post(
    "/{session_id}/approvals/{approval_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve sensitive tool execution (alias)",
    include_in_schema=False,
)
async def approve_tool_execution(
    session_id: UUID,
    approval_id: UUID,
    payload: ApprovalDecisionRequest,
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    _perm: Annotated[User, Depends(require_permission(PERM_AGENTS_APPROVE))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApprovalResponse:
    """Authorize execution of a pending approval gate."""
    approval_mgr = ApprovalManager()
    approval = await approval_mgr.get_request(db_session, approval_id, tenant_ctx.organization_id)
    if not approval or approval.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found"
        )

    res = await approval_mgr.resolve(
        db_session=db_session,
        approval=approval,
        decision=ApprovalStatus.APPROVED,
        operator_user_id=current_user.id,
        reason=payload.reason,
    )
    await db_session.commit()
    return ApprovalResponse.model_validate(res)


@router.post(
    "/sessions/{session_id}/approvals/{approval_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject sensitive tool execution",
)
@router.post(
    "/{session_id}/approvals/{approval_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject sensitive tool execution (alias)",
    include_in_schema=False,
)
async def reject_tool_execution(
    session_id: UUID,
    approval_id: UUID,
    payload: ApprovalDecisionRequest,
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    _perm: Annotated[User, Depends(require_permission(PERM_AGENTS_APPROVE))],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApprovalResponse:
    """Reject execution of a pending approval gate."""
    approval_mgr = ApprovalManager()
    approval = await approval_mgr.get_request(db_session, approval_id, tenant_ctx.organization_id)
    if not approval or approval.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found"
        )

    res = await approval_mgr.resolve(
        db_session=db_session,
        approval=approval,
        decision=ApprovalStatus.REJECTED,
        operator_user_id=current_user.id,
        reason=payload.reason,
    )
    await db_session.commit()
    return ApprovalResponse.model_validate(res)

"""FastAPI REST API routes for Enterprise Governance, Approvals & Risk Management."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db_session
from app.governance.api.schemas import (
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    CommentResponse,
    DecisionResponse,
    GovernancePolicyResponse,
    PolicyUpdateRequest,
    ReviewCommentCreate,
    VoteRequest,
)
from app.governance.application.approval_service import ApprovalService
from app.governance.application.decision_service import DecisionService
from app.governance.application.policy_service import PolicyService
from app.governance.application.review_service import ReviewService
from app.governance.application.risk_service import RiskService
from app.governance.domain.enums import (
    ApprovalStatus,
    ApprovalType,
    RiskLevel,
    VoteDecision,
)
from app.governance.domain.errors import (
    ApprovalExpiredError,
    ApprovalNotFoundError,
    GovernanceError,
    InvalidStateTransitionError,
    SelfApprovalError,
)
from app.governance.infrastructure.repository import GovernanceRepository
from app.rbac.catalog import (
    PERM_GOVERNANCE_APPROVE,
    PERM_GOVERNANCE_CREATE,
    PERM_GOVERNANCE_MANAGE_POLICY,
    PERM_GOVERNANCE_READ,
    PERM_GOVERNANCE_REJECT,
    PERM_GOVERNANCE_REVIEW,
    PERM_GOVERNANCE_VIEW_AUDIT,
)
from app.rbac.dependencies import require_permission
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_tenant_context

router = APIRouter(prefix="/governance", tags=["Governance & Human-in-the-Loop Workflow"])


def _get_services(
    db: AsyncSession,
) -> tuple[ApprovalService, PolicyService, ReviewService, DecisionService]:
    repo = GovernanceRepository(db)
    risk_svc = RiskService()
    policy_svc = PolicyService(repo)
    decision_svc = DecisionService(repo)
    approval_svc = ApprovalService(repo, risk_svc, policy_svc, decision_svc)
    review_svc = ReviewService(repo)
    return approval_svc, policy_svc, review_svc, decision_svc


@router.post(
    "/approvals",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(PERM_GOVERNANCE_CREATE))],
)
async def create_approval(
    body: ApprovalRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> Any:
    """Submit a sensitive operation for governance risk assessment and approval."""
    approval_svc, _, _, _ = _get_services(db)
    try:
        request = await approval_svc.create_approval_request(
            organization_id=tenant.organization_id,
            requester_id=tenant.user_id,
            request_type=body.request_type,
            resource_type=body.resource_type,
            resource_id=body.resource_id,
            action_payload=body.action_payload,
            reason=body.reason,
            context=body.context,
            risk_factors=body.risk_factors,
        )
        return request
    except GovernanceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message) from e


@router.get(
    "/approvals",
    response_model=list[ApprovalRequestResponse],
    dependencies=[Depends(require_permission(PERM_GOVERNANCE_READ))],
)
async def list_approvals(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    status: Annotated[ApprovalStatus | None, Query()] = None,
    request_type: Annotated[ApprovalType | None, Query()] = None,
    risk_level: Annotated[RiskLevel | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    """List approval requests within tenant boundary."""
    approval_svc, _, _, _ = _get_services(db)
    return await approval_svc.list_requests(
        organization_id=tenant.organization_id,
        status=status,
        request_type=request_type,
        risk_level=risk_level,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/requests/high-risk",
    response_model=list[ApprovalRequestResponse],
    dependencies=[Depends(require_permission(PERM_GOVERNANCE_READ))],
)
async def list_high_risk_approvals(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    """List high-risk and critical approval requests."""
    approval_svc, _, _, _ = _get_services(db)
    return await approval_svc.list_high_risk_requests(
        organization_id=tenant.organization_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/approvals/{id}",
    response_model=ApprovalRequestResponse,
    dependencies=[Depends(require_permission(PERM_GOVERNANCE_READ))],
)
async def get_approval(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> Any:
    """Retrieve details and votes for a specific approval request."""
    approval_svc, _, _, _ = _get_services(db)
    try:
        return await approval_svc.get_request(
            organization_id=tenant.organization_id,
            request_id=id,
        )
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from e


@router.post(
    "/approvals/{id}/review",
    response_model=CommentResponse,
    dependencies=[Depends(require_permission(PERM_GOVERNANCE_REVIEW))],
)
async def post_review_comment(
    id: uuid.UUID,
    body: ReviewCommentCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> Any:
    """Submit a discussion or review comment on an approval request."""
    approval_svc, _, review_svc, _ = _get_services(db)
    try:
        # Verify existence
        await approval_svc.get_request(tenant.organization_id, id)
        return await review_svc.add_comment(
            organization_id=tenant.organization_id,
            request_id=id,
            author_id=tenant.user_id,
            comment=body.comment,
        )
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/approvals/{id}/approve",
    response_model=ApprovalRequestResponse,
    dependencies=[Depends(require_permission(PERM_GOVERNANCE_APPROVE))],
)
async def approve_request(
    id: uuid.UUID,
    body: VoteRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> Any:
    """Cast an APPROVE vote on an approval request."""
    approval_svc, _, _, _ = _get_services(db)
    try:
        updated_req, _ = await approval_svc.cast_vote(
            organization_id=tenant.organization_id,
            request_id=id,
            reviewer_id=tenant.user_id,
            decision=VoteDecision.APPROVE,
            comment=body.comment,
        )
        return updated_req
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from e
    except SelfApprovalError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message) from e
    except (InvalidStateTransitionError, ApprovalExpiredError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message) from e


@router.post(
    "/approvals/{id}/reject",
    response_model=ApprovalRequestResponse,
    dependencies=[Depends(require_permission(PERM_GOVERNANCE_REJECT))],
)
async def reject_request(
    id: uuid.UUID,
    body: VoteRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> Any:
    """Cast a REJECT vote on an approval request."""
    approval_svc, _, _, _ = _get_services(db)
    try:
        updated_req, _ = await approval_svc.cast_vote(
            organization_id=tenant.organization_id,
            request_id=id,
            reviewer_id=tenant.user_id,
            decision=VoteDecision.REJECT,
            comment=body.comment,
        )
        return updated_req
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from e
    except SelfApprovalError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message) from e
    except (InvalidStateTransitionError, ApprovalExpiredError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message) from e


@router.post(
    "/approvals/{id}/changes-requested",
    response_model=ApprovalRequestResponse,
    dependencies=[Depends(require_permission(PERM_GOVERNANCE_REVIEW))],
)
async def request_changes(
    id: uuid.UUID,
    body: VoteRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> Any:
    """Request modifications before granting approval."""
    approval_svc, _, _, _ = _get_services(db)
    try:
        updated_req, _ = await approval_svc.cast_vote(
            organization_id=tenant.organization_id,
            request_id=id,
            reviewer_id=tenant.user_id,
            decision=VoteDecision.REQUEST_CHANGES,
            comment=body.comment,
        )
        return updated_req
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from e
    except SelfApprovalError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message) from e
    except (InvalidStateTransitionError, ApprovalExpiredError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message) from e


@router.post(
    "/approvals/{id}/cancel",
    response_model=ApprovalRequestResponse,
    dependencies=[Depends(require_permission(PERM_GOVERNANCE_CREATE))],
)
async def cancel_approval(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> Any:
    """Cancel a pending approval request."""
    approval_svc, _, _, _ = _get_services(db)
    try:
        return await approval_svc.cancel_request(
            organization_id=tenant.organization_id,
            request_id=id,
            canceller_id=tenant.user_id,
        )
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message) from e
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message) from e


@router.get(
    "/policies",
    response_model=GovernancePolicyResponse,
    dependencies=[Depends(require_permission(PERM_GOVERNANCE_READ))],
)
async def get_active_policy(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> Any:
    """Fetch active organization governance policy."""
    _, policy_svc, _, _ = _get_services(db)
    return await policy_svc.get_active_policy(tenant.organization_id)


@router.put(
    "/policies",
    response_model=GovernancePolicyResponse,
    dependencies=[Depends(require_permission(PERM_GOVERNANCE_MANAGE_POLICY))],
)
async def update_governance_policy(
    body: PolicyUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> Any:
    """Update organization governance rules and bump policy version."""
    _, policy_svc, _, _ = _get_services(db)
    try:
        return await policy_svc.update_policy(
            organization_id=tenant.organization_id,
            new_rules=body.rules,
            creator_id=tenant.user_id,
        )
    except GovernanceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message) from e


@router.get(
    "/{id}/history",
    response_model=DecisionResponse,
    dependencies=[Depends(require_permission(PERM_GOVERNANCE_VIEW_AUDIT))],
)
async def get_decision_history(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
) -> Any:
    """Fetch immutable resolution record and decision hash for audit verification."""
    _, _, _, decision_svc = _get_services(db)
    dec = await decision_svc.get_decision(
        organization_id=tenant.organization_id,
        request_id=id,
    )
    if not dec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No decision record found for approval request {id}",
        )
    return dec

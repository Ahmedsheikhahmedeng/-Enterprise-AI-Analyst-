"""Approval State and UI Contract Routes — TASK 34."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.platform.dependencies import (
    check_rate_limit,
    get_correlation_ids,
)
from app.api.v1.platform.schemas.common import ApiResponse
from app.api.v1.platform.schemas.execution import ApprovalUIContract
from app.db.postgres import get_db_session
from app.models.governance import ApprovalRequestModel
from app.rbac.catalog import PERM_ORCHESTRATION_READ
from app.response_orchestration.infrastructure.repository import OrchestrationRepository
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

approvals_router = APIRouter(prefix="/ask", tags=["Platform Approvals"])


@approvals_router.get(
    "/{execution_id}/approval",
    response_model=ApiResponse[ApprovalUIContract],
    summary="Get human approval state for an execution",
    dependencies=[Depends(check_rate_limit("approval_status", limit_per_minute=120))],
)
async def get_execution_approval_state(
    execution_id: uuid.UUID,
    request: Request,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[ApprovalUIContract]:
    """Retrieve human-in-the-loop approval state adhering to the frontend UX contract."""
    req_id, tr_id = get_correlation_ids(request)

    # 1. Check execution existence and tenant ownership
    repo = OrchestrationRepository(session)
    record = await repo.get_execution(execution_id, tenant_context.organization_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found or access denied.",
        )

    if record.decision != "APPROVAL_REQUIRED":
        contract = ApprovalUIContract(
            approval_required=False,
            status="NOT_REQUIRED",
        )
        return ApiResponse.ok(data=contract, request_id=req_id, trace_id=tr_id)

    # 2. Look up associated approval request in governance table if any
    stmt = (
        select(ApprovalRequestModel)
        .where(
            ApprovalRequestModel.resource_id == str(execution_id),
            ApprovalRequestModel.organization_id == tenant_context.organization_id,
        )
        .order_by(ApprovalRequestModel.created_at.desc())
        .limit(1)
    )
    gov_req = (await session.execute(stmt)).scalar_one_or_none()

    if gov_req:
        contract = ApprovalUIContract(
            approval_required=True,
            approval_request_id=str(gov_req.id),
            risk_level=gov_req.risk_level,
            expires_at=gov_req.expires_at.isoformat() if gov_req.expires_at else None,
            required_approvers=1,
            status=gov_req.status,
        )
    else:
        contract = ApprovalUIContract(
            approval_required=True,
            risk_level="HIGH",
            required_approvers=1,
            status="PENDING",
        )

    return ApiResponse.ok(data=contract, request_id=req_id, trace_id=tr_id)

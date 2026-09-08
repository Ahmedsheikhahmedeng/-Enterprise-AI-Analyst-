"""Execution History and Collection Routes — TASK 34."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.platform.dependencies import (
    check_rate_limit,
    get_correlation_ids,
)
from app.api.v1.platform.schemas.common import ApiResponse, PaginatedData
from app.api.v1.platform.schemas.execution import ExecutionSummary
from app.db.postgres import get_db_session
from app.models.orchestration import OrchestrationExecutionModel
from app.rbac.catalog import PERM_ORCHESTRATION_READ
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

executions_router = APIRouter(prefix="/executions", tags=["Platform Executions"])


@executions_router.get(
    "",
    response_model=ApiResponse[PaginatedData[ExecutionSummary]],
    summary="List historical query executions with filters and pagination",
    dependencies=[Depends(check_rate_limit("executions_history", limit_per_minute=120))],
)
async def list_executions(
    request: Request,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    cursor: Annotated[str | None, Query(description="Cursor token")] = None,
    status_filter: Annotated[
        str | None, Query(alias="status", description="Execution status filter")
    ] = None,
    mode_filter: Annotated[
        str | None, Query(alias="mode", description="Execution mode filter")
    ] = None,
    decision_filter: Annotated[
        str | None, Query(alias="decision", description="Decision filter")
    ] = None,
    date_from: Annotated[
        datetime | None, Query(description="Filter executions started on or after")
    ] = None,
    date_to: Annotated[
        datetime | None, Query(description="Filter executions started on or before")
    ] = None,
    min_confidence: Annotated[
        float | None, Query(ge=0.0, le=1.0, description="Minimum confidence score")
    ] = None,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_READ))
    ] = None,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> ApiResponse[PaginatedData[ExecutionSummary]]:
    """Retrieve execution history filtered strictly by tenant boundary."""
    req_id, tr_id = get_correlation_ids(request)

    # Base query restricted to caller's tenant
    query = select(OrchestrationExecutionModel).where(
        OrchestrationExecutionModel.organization_id == tenant_context.organization_id
    )

    if status_filter:
        query = query.where(OrchestrationExecutionModel.status == status_filter.upper())
    if mode_filter:
        query = query.where(OrchestrationExecutionModel.mode == mode_filter.upper())
    if decision_filter:
        query = query.where(OrchestrationExecutionModel.decision == decision_filter.upper())
    if date_from:
        query = query.where(OrchestrationExecutionModel.started_at >= date_from)
    if date_to:
        query = query.where(OrchestrationExecutionModel.started_at <= date_to)
    if min_confidence is not None:
        query = query.where(OrchestrationExecutionModel.confidence_score >= min_confidence)

    # Count query
    count_stmt = select(func.count()).select_from(query.subquery())
    total_count = (await session.execute(count_stmt)).scalar_one()

    # Pagination query
    offset = (page - 1) * page_size
    query = (
        query.order_by(OrchestrationExecutionModel.started_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    results = (await session.execute(query)).scalars().all()

    items = [
        ExecutionSummary(
            id=r.id,
            query=r.query,
            status=r.status,
            mode=r.mode,
            decision=r.decision,
            confidence_score=float(r.confidence_score),
            evidence_coverage=float(r.evidence_coverage),
            created_at=r.started_at,
            completed_at=r.completed_at,
        )
        for r in results
    ]

    has_more = offset + len(items) < total_count
    next_cursor = str(items[-1].id) if has_more and items else None

    paginated_data = PaginatedData[ExecutionSummary](
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        cursor=next_cursor,
        has_more=has_more,
    )

    return ApiResponse.ok(data=paginated_data, request_id=req_id, trace_id=tr_id)

"""Admin System Health, Metrics and Global Execution Overview Routes — TASK 34."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.platform.dependencies import get_correlation_ids
from app.api.v1.platform.schemas.common import ApiResponse, PaginatedData
from app.api.v1.platform.schemas.execution import ExecutionSummary
from app.db.postgres import check_database_connectivity, get_db_session
from app.db.qdrant import check_qdrant_connectivity
from app.db.redis import check_redis_connectivity
from app.models.orchestration import OrchestrationExecutionModel
from app.observability.instrumentation.platform import get_platform_instrumentation
from app.rbac.catalog import PERM_ORCHESTRATION_MANAGE
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

admin_router = APIRouter(prefix="/admin/system", tags=["Platform Admin"])


@admin_router.get(
    "/health",
    response_model=ApiResponse[dict[str, Any]],
    summary="Admin system health check verifying core services and connections",
)
async def get_system_health(
    request: Request,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_MANAGE))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[dict[str, Any]]:
    """Check connectivity across PostgreSQL, Redis, Qdrant, and active SSE streams."""
    req_id, tr_id = get_correlation_ids(request)

    engine = getattr(request.app.state, "db_engine", None)
    redis_cli = getattr(request.app.state, "redis_client", None)
    qdrant_cli = getattr(request.app.state, "qdrant_client", None)

    db_ok = await check_database_connectivity(engine) if engine else True
    redis_ok = await check_redis_connectivity(redis_cli) if redis_cli else True
    qdrant_ok = await check_qdrant_connectivity(qdrant_cli) if qdrant_cli else True

    instrumentation = get_platform_instrumentation()
    active_sse = instrumentation._get_active_sse_count()

    overall_status = "HEALTHY" if (db_ok and redis_ok and qdrant_ok) else "DEGRADED"

    health_data = {
        "status": overall_status,
        "subsystems": {
            "postgres": "ok" if db_ok else "unreachable",
            "redis": "ok" if redis_ok else "unreachable",
            "qdrant": "ok" if qdrant_ok else "unreachable",
        },
        "sse": {
            "active_connections": active_sse,
        },
    }

    return ApiResponse.ok(data=health_data, request_id=req_id, trace_id=tr_id)


@admin_router.get(
    "/metrics",
    response_model=ApiResponse[dict[str, Any]],
    summary="Admin platform metrics overview",
)
async def get_system_metrics(
    request: Request,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_MANAGE))
    ],
) -> ApiResponse[dict[str, Any]]:
    """Retrieve platform level performance and stream metrics."""
    req_id, tr_id = get_correlation_ids(request)
    instrumentation = get_platform_instrumentation()
    active_sse = instrumentation._get_active_sse_count()

    metrics_data = {
        "sse_active_connections": active_sse,
        "collected_at": req_id,
    }

    return ApiResponse.ok(data=metrics_data, request_id=req_id, trace_id=tr_id)


@admin_router.get(
    "/executions",
    response_model=ApiResponse[PaginatedData[ExecutionSummary]],
    summary="Admin system-wide executions view across organizations",
)
async def get_system_executions(
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_MANAGE))
    ] = None,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
) -> ApiResponse[PaginatedData[ExecutionSummary]]:
    """Privileged admin view of recent executions across the platform."""
    req_id, tr_id = get_correlation_ids(request)

    count_stmt = select(func.count(OrchestrationExecutionModel.id))
    total_count = (await session.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    stmt = (
        select(OrchestrationExecutionModel)
        .order_by(OrchestrationExecutionModel.started_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    records = (await session.execute(stmt)).scalars().all()

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
        for r in records
    ]

    has_more = offset + len(items) < total_count
    paginated_data = PaginatedData[ExecutionSummary](
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )

    return ApiResponse.ok(data=paginated_data, request_id=req_id, trace_id=tr_id)


platform_health_router = APIRouter(prefix="/platform", tags=["Platform Health"])


@platform_health_router.get(
    "/health",
    response_model=ApiResponse[dict[str, Any]],
    summary="Platform liveness probe",
)
async def get_platform_liveness(request: Request) -> ApiResponse[dict[str, Any]]:
    """Liveness probe returning HTTP 200 for process monitoring."""
    from app.core.config import get_settings

    settings = get_settings()
    req_id, tr_id = get_correlation_ids(request)
    return ApiResponse.ok(
        data={"status": "ok", "service": "enterprise-ai-analyst", "version": settings.APP_VERSION},
        request_id=req_id,
        trace_id=tr_id,
    )


@platform_health_router.get(
    "/ready",
    response_model=ApiResponse[dict[str, Any]],
    summary="Platform readiness probe",
)
async def get_platform_readiness(request: Request) -> ApiResponse[dict[str, Any]]:
    """Readiness probe verifying database, redis, and qdrant connectivity."""
    req_id, tr_id = get_correlation_ids(request)
    engine = getattr(request.app.state, "db_engine", None)
    redis_cli = getattr(request.app.state, "redis_client", None)
    qdrant_cli = getattr(request.app.state, "qdrant_client", None)

    db_ok = await check_database_connectivity(engine) if engine else True
    redis_ok = await check_redis_connectivity(redis_cli) if redis_cli else True
    qdrant_ok = await check_qdrant_connectivity(qdrant_cli) if qdrant_cli else True

    overall = "ready" if (db_ok and redis_ok and qdrant_ok) else "degraded"
    return ApiResponse.ok(
        data={
            "status": overall,
            "database": "ok" if db_ok else "unreachable",
            "redis": "ok" if redis_ok else "unreachable",
            "qdrant": "ok" if qdrant_ok else "unreachable",
        },
        request_id=req_id,
        trace_id=tr_id,
    )

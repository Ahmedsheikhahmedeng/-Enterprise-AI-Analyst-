"""FastAPI REST router for Production Observability, Distributed Tracing & Monitoring."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.observability.exceptions import ObservabilityAuthorizationError
from app.observability.schemas import (
    AlertsResponse,
    DependencyHealthResponse,
    ObservabilitySummaryResponse,
    SLOSummaryResponse,
    TraceDetailResponse,
)
from app.observability.service import ObservabilityService, get_observability_service
from app.rbac.catalog import (
    PERM_OBSERVABILITY_HEALTH,
    PERM_OBSERVABILITY_METRICS,
    PERM_OBSERVABILITY_READ,
)
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

router = APIRouter(prefix="/observability", tags=["Observability"])


def resolve_observability_service(request: Request) -> ObservabilityService:
    """Resolve or construct singleton ObservabilityService from request or global instance."""
    existing = getattr(request.app.state, "observability_service", None)
    if existing is not None and isinstance(existing, ObservabilityService):
        return existing
    service = get_observability_service()
    request.app.state.observability_service = service
    return service


@router.get(
    "/summary",
    response_model=ObservabilitySummaryResponse,
    summary="Get aggregated operational platform telemetry summary",
)
async def get_summary(
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_OBSERVABILITY_READ))],
    service: Annotated[ObservabilityService, Depends(resolve_observability_service)],
) -> ObservabilitySummaryResponse:
    """Retrieve top-level platform execution telemetry, percentiles, token usage, and cost."""
    return service.get_summary()


@router.get(
    "/metrics",
    summary="Export operational metrics in Prometheus exposition format",
)
async def get_metrics(
    tenant: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_OBSERVABILITY_METRICS))
    ],
    service: Annotated[ObservabilityService, Depends(resolve_observability_service)],
) -> Response:
    """Export Prometheus-formatted metric series without leaking tenant-sensitive data."""
    exposition = service.export_prometheus_metrics()
    return Response(
        content=exposition,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get(
    "/health",
    response_model=DependencyHealthResponse,
    summary="Detailed health check of infrastructure backing services",
)
async def get_health(
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_OBSERVABILITY_HEALTH))],
    service: Annotated[ObservabilityService, Depends(resolve_observability_service)],
) -> DependencyHealthResponse:
    """Probe PostgreSQL, Redis, Qdrant, and LLM provider connectivity and latencies."""
    return await service.get_dependency_health()


@router.get(
    "/slos",
    response_model=SLOSummaryResponse,
    summary="Evaluate Service Level Objectives and remaining error budgets",
)
async def get_slos(
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_OBSERVABILITY_READ))],
    service: Annotated[ObservabilityService, Depends(resolve_observability_service)],
) -> SLOSummaryResponse:
    """Check SLO targets (availability, latency, SQL/RAG/LLM success rates) and error budgets."""
    return service.get_slo_evaluation()


@router.get(
    "/alerts",
    response_model=AlertsResponse,
    summary="Scan operational alerts conditions and active anomalies",
)
async def get_alerts(
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_OBSERVABILITY_READ))],
    service: Annotated[ObservabilityService, Depends(resolve_observability_service)],
) -> AlertsResponse:
    """Inspect active operational alerts such as high error rates or high latencies."""
    return service.get_active_alerts()


@router.get(
    "/traces/{trace_id}",
    response_model=TraceDetailResponse,
    summary="Retrieve distributed execution spans for a specific trace",
)
async def get_trace_detail(
    trace_id: str,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_OBSERVABILITY_READ))],
    service: Annotated[ObservabilityService, Depends(resolve_observability_service)],
) -> TraceDetailResponse:
    """Retrieve hierarchical spans for a distributed trace, strictly enforcing tenant isolation."""
    try:
        detail = service.get_trace_detail(trace_id=trace_id, tenant_org_id=tenant.organization_id)
    except ObservabilityAuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace with ID '{trace_id}' not found or has expired from buffer.",
        )
    return detail

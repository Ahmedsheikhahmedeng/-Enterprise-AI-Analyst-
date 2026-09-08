"""FastAPI REST API routes for SRE, SLIs/SLOs, Alert Lifecycle, Incidents, and Release Safety."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db_session
from app.rbac.catalog import (
    PERM_SRE_ALERT_MANAGE,
    PERM_SRE_ALERT_READ,
    PERM_SRE_INCIDENT_MANAGE,
    PERM_SRE_INCIDENT_READ,
    PERM_SRE_MAINTENANCE_MANAGE,
    PERM_SRE_RELEASE_GATE_READ,
    PERM_SRE_RUNBOOK_MANAGE,
    PERM_SRE_RUNBOOK_READ,
    PERM_SRE_SLO_MANAGE,
    PERM_SRE_SLO_READ,
)
from app.rbac.dependencies import require_permission
from app.sre.dependencies import check_all_dependencies
from app.sre.incidents import InvalidIncidentTransitionError
from app.sre.repository import SRERepository
from app.sre.runbooks import PublishedRunbookImmutableError, UnsafeRunbookActionError
from app.sre.schemas import (
    AlertAcknowledgeRequest,
    AlertEventResponse,
    AlertIngest,
    AlertNoiseResponse,
    AlertResolveRequest,
    AlertResponse,
    AlertSuppressRequest,
    DependencyMatrixResponse,
    IncidentAssignRequest,
    IncidentCreate,
    IncidentEventResponse,
    IncidentMetricsResponse,
    IncidentNoteCreate,
    IncidentResponse,
    IncidentStatusUpdate,
    MaintenanceWindowCreate,
    MaintenanceWindowResponse,
    OperationalReadinessResponse,
    PlatformOverviewResponse,
    ReleaseGateEvaluateRequest,
    ReleaseGateResponse,
    RunbookCreate,
    RunbookResponse,
    RunbookUpdate,
    SLICreate,
    SLIResponse,
    SLOCreate,
    SLOResponse,
)
from app.sre.service import SREService
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_tenant_context

router = APIRouter(prefix="/sre", tags=["SRE & Operational Observability"])


def _get_service(db: AsyncSession) -> SREService:
    return SREService(SRERepository(db))


# ---------------------------------------------------------------------------
# SLIs
# ---------------------------------------------------------------------------
@router.get(
    "/slis",
    response_model=list[SLIResponse],
    summary="List SLIs",
    dependencies=[Depends(require_permission(PERM_SRE_SLO_READ))],
)
async def list_slis(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: str | None = Query(None),
) -> list[SLIResponse]:
    svc = _get_service(db)
    slis = await svc.repo.list_slis(tenant.organization_id, service)
    return [SLIResponse.model_validate(s) for s in slis]


@router.post(
    "/slis",
    response_model=SLIResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create SLI Definition",
    dependencies=[Depends(require_permission(PERM_SRE_SLO_MANAGE))],
)
async def create_sli(
    data: SLICreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SLIResponse:
    svc = _get_service(db)
    sli = await svc.create_sli(data, tenant.organization_id)
    return SLIResponse.model_validate(sli)


# ---------------------------------------------------------------------------
# SLOs
# ---------------------------------------------------------------------------
@router.get(
    "/slos",
    response_model=list[SLOResponse],
    summary="List SLOs",
    dependencies=[Depends(require_permission(PERM_SRE_SLO_READ))],
)
async def list_slos(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: str | None = Query(None),
) -> list[SLOResponse]:
    svc = _get_service(db)
    slos = await svc.repo.list_slos(tenant.organization_id, service)
    return [SLOResponse.model_validate(s) for s in slos]


@router.post(
    "/slos",
    response_model=SLOResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create SLO Target",
    dependencies=[Depends(require_permission(PERM_SRE_SLO_MANAGE))],
)
async def create_slo(
    data: SLOCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SLOResponse:
    svc = _get_service(db)
    slo = await svc.create_slo(data, tenant.organization_id)
    return SLOResponse.model_validate(slo)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
@router.get(
    "/alerts",
    response_model=list[AlertResponse],
    summary="List Alerts",
    dependencies=[Depends(require_permission(PERM_SRE_ALERT_READ))],
)
async def list_alerts(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> list[AlertResponse]:
    svc = _get_service(db)
    alerts = await svc.repo.list_alerts(
        org_id=tenant.organization_id,
        service=service,
        status=status_filter,
        severity=severity,
        limit=limit,
    )
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post(
    "/alerts",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest Alert Event",
    dependencies=[Depends(require_permission(PERM_SRE_ALERT_MANAGE))],
)
async def ingest_alert(
    data: AlertIngest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AlertResponse:
    svc = _get_service(db)
    alert = await svc.ingest_alert(data, tenant.organization_id)
    return AlertResponse.model_validate(alert)


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=AlertResponse,
    summary="Acknowledge Alert",
    dependencies=[Depends(require_permission(PERM_SRE_ALERT_MANAGE))],
)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    req: AlertAcknowledgeRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AlertResponse:
    svc = _get_service(db)
    try:
        alert = await svc.acknowledge_alert(alert_id, req, tenant.organization_id)
        return AlertResponse.model_validate(alert)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/alerts/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Resolve Alert",
    dependencies=[Depends(require_permission(PERM_SRE_ALERT_MANAGE))],
)
async def resolve_alert(
    alert_id: uuid.UUID,
    req: AlertResolveRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AlertResponse:
    svc = _get_service(db)
    try:
        alert = await svc.resolve_alert(alert_id, req, tenant.organization_id)
        return AlertResponse.model_validate(alert)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/alerts/{alert_id}/suppress",
    response_model=AlertResponse,
    summary="Suppress Alert",
    dependencies=[Depends(require_permission(PERM_SRE_ALERT_MANAGE))],
)
async def suppress_alert(
    alert_id: uuid.UUID,
    req: AlertSuppressRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AlertResponse:
    svc = _get_service(db)
    try:
        alert = await svc.suppress_alert(alert_id, req, tenant.organization_id)
        return AlertResponse.model_validate(alert)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/alerts/{alert_id}/timeline",
    response_model=list[AlertEventResponse],
    summary="View Alert Event Timeline",
    dependencies=[Depends(require_permission(PERM_SRE_ALERT_READ))],
)
async def get_alert_timeline(
    alert_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AlertEventResponse]:
    svc = _get_service(db)
    events = await svc.repo.list_alert_events(alert_id, tenant.organization_id)
    return [AlertEventResponse.model_validate(e) for e in events]


@router.get(
    "/alerts/noise",
    response_model=AlertNoiseResponse,
    summary="Calculate Alert Noise Ratio",
    dependencies=[Depends(require_permission(PERM_SRE_ALERT_READ))],
)
async def get_alert_noise(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AlertNoiseResponse:
    svc = _get_service(db)
    return await svc.get_alert_noise(tenant.organization_id)


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------
@router.get(
    "/incidents",
    response_model=list[IncidentResponse],
    summary="List Incidents",
    dependencies=[Depends(require_permission(PERM_SRE_INCIDENT_READ))],
)
async def list_incidents(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[IncidentResponse]:
    svc = _get_service(db)
    incidents = await svc.repo.list_incidents(
        org_id=tenant.organization_id,
        service=service,
        status=status_filter,
        severity=severity,
        limit=limit,
    )
    return [IncidentResponse.model_validate(i) for i in incidents]


@router.post(
    "/incidents",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Declare Incident",
    dependencies=[Depends(require_permission(PERM_SRE_INCIDENT_MANAGE))],
)
async def create_incident(
    data: IncidentCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> IncidentResponse:
    svc = _get_service(db)
    incident = await svc.create_incident(data, tenant.organization_id)
    return IncidentResponse.model_validate(incident)


@router.get(
    "/incidents/metrics",
    response_model=IncidentMetricsResponse,
    summary="Incident Operational Metrics (MTTA/MTTR)",
    dependencies=[Depends(require_permission(PERM_SRE_INCIDENT_READ))],
)
async def get_incident_metrics(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> IncidentMetricsResponse:
    svc = _get_service(db)
    return await svc.get_incident_metrics(tenant.organization_id)


@router.get(
    "/incidents/{incident_id}",
    response_model=IncidentResponse,
    summary="Get Incident Details",
    dependencies=[Depends(require_permission(PERM_SRE_INCIDENT_READ))],
)
async def get_incident(
    incident_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> IncidentResponse:
    svc = _get_service(db)
    incident = await svc.repo.get_incident(incident_id, tenant.organization_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")
    return IncidentResponse.model_validate(incident)


@router.patch(
    "/incidents/{incident_id}/status",
    response_model=IncidentResponse,
    summary="Transition Incident State",
    dependencies=[Depends(require_permission(PERM_SRE_INCIDENT_MANAGE))],
)
async def update_incident_status(
    incident_id: uuid.UUID,
    req: IncidentStatusUpdate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> IncidentResponse:
    svc = _get_service(db)
    try:
        incident = await svc.update_incident_status(incident_id, req, tenant.organization_id)
        return IncidentResponse.model_validate(incident)
    except InvalidIncidentTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/incidents/{incident_id}/assign",
    response_model=IncidentResponse,
    summary="Assign Incident Responders",
    dependencies=[Depends(require_permission(PERM_SRE_INCIDENT_MANAGE))],
)
async def assign_incident_responder(
    incident_id: uuid.UUID,
    req: IncidentAssignRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> IncidentResponse:
    svc = _get_service(db)
    try:
        incident = await svc.assign_incident_responder(incident_id, req, tenant.organization_id)
        return IncidentResponse.model_validate(incident)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/incidents/{incident_id}/notes",
    response_model=IncidentEventResponse,
    summary="Add Note to Incident Timeline",
    dependencies=[Depends(require_permission(PERM_SRE_INCIDENT_MANAGE))],
)
async def add_incident_note(
    incident_id: uuid.UUID,
    req: IncidentNoteCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> IncidentEventResponse:
    svc = _get_service(db)
    try:
        event = await svc.add_incident_note(incident_id, req, tenant.organization_id)
        return IncidentEventResponse.model_validate(event)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/incidents/{incident_id}/timeline",
    response_model=list[IncidentEventResponse],
    summary="View Incident Event Timeline",
    dependencies=[Depends(require_permission(PERM_SRE_INCIDENT_READ))],
)
async def get_incident_timeline(
    incident_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[IncidentEventResponse]:
    svc = _get_service(db)
    events = await svc.repo.list_incident_events(incident_id, tenant.organization_id)
    return [IncidentEventResponse.model_validate(e) for e in events]


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
@router.get(
    "/dependencies",
    response_model=DependencyMatrixResponse,
    summary="Inspect Dependency Health Matrix",
    dependencies=[Depends(require_permission(PERM_SRE_ALERT_READ))],
)
async def get_dependencies(
    request: Request,
) -> DependencyMatrixResponse:
    db_engine = getattr(request.app.state, "db_engine", None)
    redis_client = getattr(request.app.state, "redis_client", None)
    qdrant_client = getattr(request.app.state, "qdrant_client", None)
    return await check_all_dependencies(db_engine, redis_client, qdrant_client)


# ---------------------------------------------------------------------------
# Runbooks
# ---------------------------------------------------------------------------
@router.get(
    "/runbooks",
    response_model=list[RunbookResponse],
    summary="List Diagnostic Runbooks",
    dependencies=[Depends(require_permission(PERM_SRE_RUNBOOK_READ))],
)
async def list_runbooks(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: str | None = Query(None),
) -> list[RunbookResponse]:
    svc = _get_service(db)
    runbooks = await svc.repo.list_runbooks(tenant.organization_id, service)
    return [RunbookResponse.model_validate(r) for r in runbooks]


@router.post(
    "/runbooks",
    response_model=RunbookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Runbook",
    dependencies=[Depends(require_permission(PERM_SRE_RUNBOOK_MANAGE))],
)
async def create_runbook(
    data: RunbookCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RunbookResponse:
    svc = _get_service(db)
    try:
        runbook = await svc.create_runbook(data, tenant.organization_id)
        return RunbookResponse.model_validate(runbook)
    except UnsafeRunbookActionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch(
    "/runbooks/{runbook_id}",
    response_model=RunbookResponse,
    summary="Update Draft Runbook",
    dependencies=[Depends(require_permission(PERM_SRE_RUNBOOK_MANAGE))],
)
async def update_runbook(
    runbook_id: uuid.UUID,
    data: RunbookUpdate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RunbookResponse:
    svc = _get_service(db)
    try:
        runbook = await svc.update_runbook(runbook_id, data, tenant.organization_id)
        return RunbookResponse.model_validate(runbook)
    except PublishedRunbookImmutableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except UnsafeRunbookActionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/runbooks/{runbook_id}/publish",
    response_model=RunbookResponse,
    summary="Publish Runbook",
    dependencies=[Depends(require_permission(PERM_SRE_RUNBOOK_MANAGE))],
)
async def publish_runbook(
    runbook_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RunbookResponse:
    svc = _get_service(db)
    try:
        runbook = await svc.publish_runbook(runbook_id, tenant.organization_id)
        return RunbookResponse.model_validate(runbook)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Maintenance Windows
# ---------------------------------------------------------------------------
@router.get(
    "/maintenance",
    response_model=list[MaintenanceWindowResponse],
    summary="List Maintenance Windows",
    dependencies=[Depends(require_permission(PERM_SRE_ALERT_READ))],
)
async def list_maintenance_windows(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[MaintenanceWindowResponse]:
    svc = _get_service(db)
    mws = await svc.repo.list_maintenance_windows(tenant.organization_id)
    return [MaintenanceWindowResponse.model_validate(m) for m in mws]


@router.post(
    "/maintenance",
    response_model=MaintenanceWindowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule Maintenance Window",
    dependencies=[Depends(require_permission(PERM_SRE_MAINTENANCE_MANAGE))],
)
async def create_maintenance_window(
    data: MaintenanceWindowCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MaintenanceWindowResponse:
    svc = _get_service(db)
    mw = await svc.create_maintenance_window(data, tenant.user_id, tenant.organization_id)
    return MaintenanceWindowResponse.model_validate(mw)


# ---------------------------------------------------------------------------
# Release Safety Gates
# ---------------------------------------------------------------------------
@router.post(
    "/release-gates/evaluate",
    response_model=ReleaseGateResponse,
    summary="Evaluate Release Safety Gate",
    dependencies=[Depends(require_permission(PERM_SRE_RELEASE_GATE_READ))],
)
async def evaluate_release_gate(
    req: ReleaseGateEvaluateRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReleaseGateResponse:
    svc = _get_service(db)
    check = await svc.evaluate_release_gate(req, tenant.organization_id)
    return ReleaseGateResponse.model_validate(check)


# ---------------------------------------------------------------------------
# Dashboards & Operational Readiness
# ---------------------------------------------------------------------------
@router.get(
    "/dashboards/overview",
    response_model=PlatformOverviewResponse,
    summary="Platform Operational Overview",
    dependencies=[Depends(require_permission(PERM_SRE_ALERT_READ))],
)
async def get_platform_overview(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlatformOverviewResponse:
    svc = _get_service(db)
    return await svc.get_platform_overview(tenant.organization_id)


@router.get(
    "/readiness",
    response_model=OperationalReadinessResponse,
    summary="Operational Readiness Evaluation",
    dependencies=[Depends(require_permission(PERM_SRE_ALERT_READ))],
)
async def get_operational_readiness(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> OperationalReadinessResponse:
    svc = _get_service(db)
    return await svc.get_operational_readiness(tenant.organization_id)

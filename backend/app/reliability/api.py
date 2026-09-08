"""FastAPI REST API routes for Reliability, Chaos Engineering & Production Readiness."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db_session
from app.rbac.catalog import (
    PERM_RELIABILITY_MANAGE,
    PERM_RELIABILITY_READ,
    PERM_RELIABILITY_READINESS,
    PERM_RELIABILITY_RUN,
)
from app.rbac.dependencies import require_permission
from app.reliability.schemas import (
    ReadinessResponse,
    ReliabilityReportResponse,
    RunDetailResponse,
    RunResponse,
    RunTriggerRequest,
    ScenarioCreate,
    ScenarioResponse,
)
from app.reliability.service import ReliabilityService
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_tenant_context

reliability_router = APIRouter(
    prefix="/reliability", tags=["Production Reliability & Chaos Engineering"]
)


def _get_service(db: AsyncSession, tenant: TenantContext) -> ReliabilityService:
    return ReliabilityService(db, tenant.organization_id)


# -----------------------------------------------------------------------------
# Scenarios
# -----------------------------------------------------------------------------
@reliability_router.get(
    "/scenarios",
    response_model=list[ScenarioResponse],
    summary="List available reliability and chaos scenarios",
    dependencies=[Depends(require_permission(PERM_RELIABILITY_READ))],
)
async def list_scenarios(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    category: str | None = Query(None, description="Optional category filter"),
) -> list[ScenarioResponse]:
    svc = _get_service(db, tenant)
    return await svc.list_scenarios(category=category)


@reliability_router.get(
    "/scenarios/{scenario_id}",
    response_model=ScenarioResponse,
    summary="Get scenario details",
    dependencies=[Depends(require_permission(PERM_RELIABILITY_READ))],
)
async def get_scenario(
    scenario_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScenarioResponse:
    svc = _get_service(db, tenant)
    scenario = await svc.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    return scenario


@reliability_router.post(
    "/scenarios",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new reliability scenario",
    dependencies=[Depends(require_permission(PERM_RELIABILITY_MANAGE))],
)
async def create_scenario(
    payload: ScenarioCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScenarioResponse:
    svc = _get_service(db, tenant)
    return await svc.create_scenario(payload)


# -----------------------------------------------------------------------------
# Runs & Chaos Triggering
# -----------------------------------------------------------------------------
@reliability_router.post(
    "/runs",
    response_model=RunDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger a non-production chaos scenario execution",
    dependencies=[Depends(require_permission(PERM_RELIABILITY_RUN))],
)
async def trigger_run(
    payload: RunTriggerRequest,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RunDetailResponse:
    if payload.environment.lower() in ("prod", "production"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chaos execution is strictly prohibited in production environments.",
        )

    svc = _get_service(db, tenant)
    try:
        return await svc.run_scenario(
            scenario_id=payload.scenario_id,
            environment=payload.environment,
            actor_id=tenant.user_id,
            parameter_overrides=payload.parameters_override,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@reliability_router.get(
    "/runs",
    response_model=list[RunResponse],
    summary="List historical chaos runs",
    dependencies=[Depends(require_permission(PERM_RELIABILITY_READ))],
)
async def list_runs(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(50, ge=1, le=200),
) -> list[RunResponse]:
    svc = _get_service(db, tenant)
    return await svc.list_runs(limit=limit)


@reliability_router.get(
    "/runs/{run_id}",
    response_model=RunDetailResponse,
    summary="Get detailed run report with faults and assertions",
    dependencies=[Depends(require_permission(PERM_RELIABILITY_READ))],
)
async def get_run_detail(
    run_id: str,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RunDetailResponse:
    svc = _get_service(db, tenant)
    detail = await svc.get_run_detail(run_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )
    return detail


# -----------------------------------------------------------------------------
# Production Readiness & Reports
# -----------------------------------------------------------------------------
@reliability_router.get(
    "/readiness",
    response_model=ReadinessResponse,
    summary="Get current Production Readiness decision and evaluation factors",
    dependencies=[Depends(require_permission(PERM_RELIABILITY_READINESS))],
)
async def get_readiness(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReadinessResponse:
    svc = _get_service(db, tenant)
    return await svc.get_latest_readiness()


@reliability_router.get(
    "/report",
    response_model=ReliabilityReportResponse,
    summary="Get executive summary report of reliability validation evidence",
    dependencies=[Depends(require_permission(PERM_RELIABILITY_READ))],
)
async def get_report(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReliabilityReportResponse:
    svc = _get_service(db, tenant)
    return await svc.generate_full_report()

"""FastAPI routes for Enterprise Productization, Diagnostics, and Readiness."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.postgres import get_db_session
from app.models.user import User
from app.product.diagnostics import DiagnosticReport
from app.product.health import SystemHealthSummary
from app.product.journeys import JourneyExecutionResult
from app.product.reports import ProductionReadinessMatrix, ReleaseManifest
from app.product.scoring import ProductReadinessReport
from app.product.service import ProductService
from app.product.workflows import WorkflowAuditSummary
from app.rbac.catalog import PERM_ORGANIZATION_MANAGE, PERM_ORGANIZATION_READ
from app.rbac.dependencies import require_permission
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_tenant_context

product_router = APIRouter(prefix="/product", tags=["Productization & Governance"])


@product_router.get(
    "/health",
    response_model=SystemHealthSummary,
    summary="System Health Aggregator",
    description="Aggregates operational health across DB, Redis, Vector store, Workers, Gateway, and FinOps.",
)
async def get_system_health(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SystemHealthSummary:
    service = ProductService(db)
    return await service.get_health()


@product_router.get(
    "/manifest",
    response_model=ReleaseManifest,
    summary="Release Manifest",
    description="Returns build timestamp, git commit, database revision, and enabled enterprise features.",
)
async def get_release_manifest(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReleaseManifest:
    service = ProductService(db)
    return await service.get_manifest()


@product_router.get(
    "/diagnostics",
    response_model=DiagnosticReport,
    summary="Deep System Diagnostics",
    description="Administrator-only diagnostics on migration state, feature readiness, and verification history.",
    dependencies=[Depends(require_permission(PERM_ORGANIZATION_MANAGE))],
)
async def get_diagnostics(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> DiagnosticReport:
    service = ProductService(db)
    return await service.get_diagnostics()


@product_router.get(
    "/readiness",
    response_model=ProductReadinessReport,
    summary="Enterprise Product Readiness Score",
    description="Computes weighted readiness score and evaluates hard blocker triggers across 9 categories.",
    dependencies=[Depends(require_permission(PERM_ORGANIZATION_READ))],
)
async def get_readiness_report(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> ProductReadinessReport:
    service = ProductService(db)
    return await service.evaluate_readiness()


@product_router.get(
    "/matrix",
    response_model=ProductionReadinessMatrix,
    summary="Production Readiness Matrix",
    description="Detailed breakdown of the 12 core platform categories and their verification status.",
    dependencies=[Depends(require_permission(PERM_ORGANIZATION_READ))],
)
async def get_readiness_matrix(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> ProductionReadinessMatrix:
    service = ProductService(db)
    return await service.get_readiness_matrix()


@product_router.get(
    "/workflows/audit",
    response_model=WorkflowAuditSummary,
    summary="Workflow State Machine Audit",
    description="Audits all registered domain state machines to ensure zero unreachable or impossible states.",
    dependencies=[Depends(require_permission(PERM_ORGANIZATION_MANAGE))],
)
async def audit_workflows(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> WorkflowAuditSummary:
    service = ProductService(db)
    return await service.audit_workflows()


@product_router.post(
    "/journeys/{journey_id}/run",
    response_model=JourneyExecutionResult,
    status_code=status.HTTP_200_OK,
    summary="Execute Canonical User Journey",
    description="Runs deterministic verification for a canonical journey (J1..J14).",
    dependencies=[Depends(require_permission(PERM_ORGANIZATION_MANAGE))],
)
async def run_journey(
    journey_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    tenant_ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> JourneyExecutionResult:
    service = ProductService(db)
    return await service.run_journey(journey_id)

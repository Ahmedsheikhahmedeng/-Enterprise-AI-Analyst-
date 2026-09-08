"""REST API endpoints for enterprise report generation, versioning, and exports."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db_session
from app.rbac.catalog import (
    PERM_REPORTS_ARCHIVE,
    PERM_REPORTS_CREATE,
    PERM_REPORTS_EXPORT,
    PERM_REPORTS_PUBLISH,
    PERM_REPORTS_READ,
)
from app.reports.schemas import (
    CreateReportFromAnalysisRequest,
    ReportListItemResponse,
    ReportListResponse,
    ReportResponse,
)
from app.reports.service import ReportService
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

router = APIRouter(prefix="/reports", tags=["Reports"])


def get_report_service(request: Request) -> ReportService:
    """Resolve or construct singleton ReportService from application state."""
    existing = getattr(request.app.state, "report_service", None)
    if existing is not None and isinstance(existing, ReportService):
        return existing
    service = ReportService()
    request.app.state.report_service = service
    return service


@router.post(
    "/from-analysis",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create enterprise report from analysis run",
)
async def create_report_from_analysis(
    payload: CreateReportFromAnalysisRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_REPORTS_CREATE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportResponse:
    """Synthesize and persist a structured report from a completed analysis run."""
    report, version_rec, doc = await service.create_report_from_analysis(
        session=session,
        organization_id=tenant.organization_id,
        analysis_run_id=payload.analysis_run_id,
        title=payload.title,
        user_id=tenant.user_id,
        subtitle=payload.subtitle,
        template=payload.template,
    )
    return ReportResponse(
        report_id=report.id,
        organization_id=report.organization_id,
        title=report.title,
        status=report.status,
        version=version_rec.version_number,
        content_hash=version_rec.content_hash,
        created_at=report.created_at,
        updated_at=report.updated_at,
        published_at=report.published_at,
        document=doc.to_dict(),
    )


@router.get(
    "",
    response_model=ReportListResponse,
    summary="List tenant reports",
)
async def list_reports(
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_REPORTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReportService, Depends(get_report_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    report_status: str | None = Query(None, alias="status"),
) -> ReportListResponse:
    """Retrieve paginated collection of reports belonging strictly to authenticated tenant."""
    items, total = await service.list_reports(
        session=session,
        organization_id=tenant.organization_id,
        page=page,
        page_size=page_size,
        status=report_status,
    )
    return ReportListResponse(
        items=[
            ReportListItemResponse(
                report_id=r.id,
                organization_id=r.organization_id,
                title=r.title,
                status=r.status,
                current_version=r.current_version,
                created_at=r.created_at,
                published_at=r.published_at,
            )
            for r in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get current report",
)
async def get_report(
    report_id: UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_REPORTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportResponse:
    """Retrieve active version of a report with full structured document."""
    report, version_rec, doc = await service.get_report(
        session=session,
        organization_id=tenant.organization_id,
        report_id=report_id,
        user_id=tenant.user_id,
    )
    return ReportResponse(
        report_id=report.id,
        organization_id=report.organization_id,
        title=report.title,
        status=report.status,
        version=version_rec.version_number,
        content_hash=version_rec.content_hash,
        created_at=report.created_at,
        updated_at=report.updated_at,
        published_at=report.published_at,
        document=doc.to_dict(),
    )


@router.get(
    "/{report_id}/versions/{version}",
    response_model=ReportResponse,
    summary="Get specific report version",
)
async def get_report_version(
    report_id: UUID,
    version: int,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_REPORTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> ReportResponse:
    """Retrieve a specific historical version of a report."""
    report, version_rec, doc = await service.get_report(
        session=session,
        organization_id=tenant.organization_id,
        report_id=report_id,
        version_number=version,
        user_id=tenant.user_id,
    )
    return ReportResponse(
        report_id=report.id,
        organization_id=report.organization_id,
        title=report.title,
        status=version_rec.status,
        version=version_rec.version_number,
        content_hash=version_rec.content_hash,
        created_at=version_rec.created_at,
        updated_at=report.updated_at,
        published_at=version_rec.published_at,
        document=doc.to_dict(),
    )


@router.post(
    "/{report_id}/publish",
    response_model=ReportResponse,
    summary="Publish report version",
)
async def publish_report(
    report_id: UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_REPORTS_PUBLISH))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReportService, Depends(get_report_service)],
    version: int | None = Query(None),
) -> ReportResponse:
    """Publish report version to make it permanently immutable."""
    report, version_rec, doc = await service.publish_report(
        session=session,
        organization_id=tenant.organization_id,
        report_id=report_id,
        version_number=version,
        user_id=tenant.user_id,
    )
    return ReportResponse(
        report_id=report.id,
        organization_id=report.organization_id,
        title=report.title,
        status=report.status,
        version=version_rec.version_number,
        content_hash=version_rec.content_hash,
        created_at=report.created_at,
        updated_at=report.updated_at,
        published_at=report.published_at,
        document=doc.to_dict(),
    )


@router.post(
    "/{report_id}/archive",
    summary="Archive report",
)
async def archive_report(
    report_id: UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_REPORTS_ARCHIVE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReportService, Depends(get_report_service)],
) -> dict[str, Any]:
    """Archive an active report."""
    report = await service.archive_report(
        session=session,
        organization_id=tenant.organization_id,
        report_id=report_id,
        user_id=tenant.user_id,
    )
    return {"report_id": str(report.id), "status": report.status}


@router.get(
    "/{report_id}/export/markdown",
    summary="Export report as Markdown",
)
async def export_markdown(
    report_id: UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_REPORTS_EXPORT))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReportService, Depends(get_report_service)],
    version: int | None = Query(None),
) -> Response:
    """Export report in Markdown format."""
    content, filename, media_type = await service.export_report(
        session=session,
        organization_id=tenant.organization_id,
        report_id=report_id,
        export_format="markdown",
        version_number=version,
        user_id=tenant.user_id,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{report_id}/export/html",
    summary="Export report as HTML",
)
async def export_html(
    report_id: UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_REPORTS_EXPORT))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReportService, Depends(get_report_service)],
    version: int | None = Query(None),
) -> Response:
    """Export report in standalone HTML format."""
    content, filename, media_type = await service.export_report(
        session=session,
        organization_id=tenant.organization_id,
        report_id=report_id,
        export_format="html",
        version_number=version,
        user_id=tenant.user_id,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get(
    "/{report_id}/export/pdf",
    summary="Export report as PDF",
)
async def export_pdf(
    report_id: UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_REPORTS_EXPORT))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReportService, Depends(get_report_service)],
    version: int | None = Query(None),
) -> Response:
    """Export report as deterministic A4 PDF document."""
    content, filename, media_type = await service.export_report(
        session=session,
        organization_id=tenant.organization_id,
        report_id=report_id,
        export_format="pdf",
        version_number=version,
        user_id=tenant.user_id,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{report_id}/export/csv",
    summary="Export report data as CSV",
)
async def export_csv(
    report_id: UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_REPORTS_EXPORT))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[ReportService, Depends(get_report_service)],
    version: int | None = Query(None),
    table_id: str | None = Query(None),
) -> Response:
    """Export structured tables from report in CSV format."""
    content, filename, media_type = await service.export_report(
        session=session,
        organization_id=tenant.organization_id,
        report_id=report_id,
        export_format="csv",
        version_number=version,
        table_id=table_id,
        user_id=tenant.user_id,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

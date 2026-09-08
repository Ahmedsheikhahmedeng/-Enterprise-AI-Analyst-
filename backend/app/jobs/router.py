"""FastAPI router for background job management endpoints."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db_session
from app.jobs.schemas import (
    JobCancelRequest,
    JobCreateRequest,
    JobHealthResponse,
    JobListResponse,
    JobResponse,
    JobRetryRequest,
)
from app.jobs.service import JobService
from app.rbac.catalog import (
    PERM_JOBS_CANCEL,
    PERM_JOBS_CREATE,
    PERM_JOBS_READ,
    PERM_JOBS_RETRY,
)
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

router = APIRouter(prefix="/jobs", tags=["Background Jobs"])


def get_job_service(request: Request) -> JobService:
    """Resolve or construct singleton JobService attached to application state."""
    existing = getattr(request.app.state, "job_service", None)
    if existing is not None and isinstance(existing, JobService):
        return existing

    redis_client = getattr(request.app.state, "redis_client", None)
    service = JobService(redis_client=redis_client)
    request.app.state.job_service = service
    return service


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue new background job",
)
async def create_job(
    payload: JobCreateRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_JOBS_CREATE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    """Validate, deduplicate, and enqueue a new background job."""
    job = await service.create_job(
        db=session,
        request=payload,
        organization_id=tenant.organization_id,
        created_by=tenant.user_id,
    )
    return JobResponse.model_validate(job)


@router.get(
    "/health",
    response_model=JobHealthResponse,
    summary="Worker and Queue Health Status",
)
async def get_jobs_health(
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_JOBS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobHealthResponse:
    """Inspect queue depths, active workers, and stuck jobs."""
    return await service.get_health(session)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get background job status",
)
async def get_job(
    job_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_JOBS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    """Fetch status, attempt counts, diagnostics, and structured result of a job."""
    job = await service.get_job(
        db=session,
        job_id=job_id,
        organization_id=tenant.organization_id,
    )
    return JobResponse.model_validate(job)


@router.get(
    "",
    response_model=JobListResponse,
    summary="List background jobs with filtering and pagination",
)
async def list_jobs(
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_JOBS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[JobService, Depends(get_job_service)],
    status: Annotated[str | None, Query(description="Filter by job status")] = None,
    job_type: Annotated[str | None, Query(description="Filter by job type")] = None,
    created_after: Annotated[datetime | None, Query(description="Created after timestamp")] = None,
    created_before: Annotated[
        datetime | None, Query(description="Created before timestamp")
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> JobListResponse:
    """List jobs belonging to the requester's organization with pagination."""
    return await service.list_jobs(
        db=session,
        organization_id=tenant.organization_id,
        status=status,
        job_type=job_type,
        created_after=created_after,
        created_before=created_before,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    summary="Cancel background job",
)
async def cancel_job(
    job_id: uuid.UUID,
    payload: JobCancelRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_JOBS_CANCEL))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    """Cancel a queued, running, or retry_scheduled background job."""
    job = await service.cancel_job(
        db=session,
        job_id=job_id,
        organization_id=tenant.organization_id,
        reason=payload.reason or "Cancelled by user",
    )
    return JobResponse.model_validate(job)


@router.post(
    "/{job_id}/retry",
    response_model=JobResponse,
    summary="Retry failed or dead-letter background job",
)
async def retry_job(
    job_id: uuid.UUID,
    payload: JobRetryRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_JOBS_RETRY))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    """Manually re-enqueue a failed or dead_letter job."""
    job = await service.retry_job(
        db=session,
        job_id=job_id,
        organization_id=tenant.organization_id,
        force=payload.force,
    )
    return JobResponse.model_validate(job)

"""High-level JobService coordinating dispatch, status, listing, cancellation and retries."""

import uuid
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.jobs.cancellation import JobCancellationManager
from app.jobs.dispatcher import JobDispatcher
from app.jobs.exceptions import (
    InvalidJobStateTransitionError,
    JobNotFoundError,
)
from app.jobs.health import WorkerHealthMonitor
from app.jobs.lifecycle import JobLifecycleManager
from app.jobs.models import Job
from app.jobs.policies import JobSecurityPolicy
from app.jobs.queue import InMemoryJobQueue, JobQueue, RedisJobQueue
from app.jobs.schemas import (
    JobCreateRequest,
    JobHealthResponse,
    JobListResponse,
    JobResponse,
    JobStatus,
)

logger = get_logger("jobs.service")


class JobService:
    """Service facade for managing background jobs lifecycle and APIs."""

    def __init__(
        self,
        queue: JobQueue | None = None,
        redis_client: Redis | None = None,
    ) -> None:
        self.redis_client = redis_client
        if queue is not None:
            self.queue = queue
        elif redis_client is not None:
            self.queue = RedisJobQueue(redis_client)
        else:
            self.queue = InMemoryJobQueue()

        self.dispatcher = JobDispatcher(self.queue)

    async def create_job(
        self,
        db: AsyncSession,
        request: JobCreateRequest,
        organization_id: uuid.UUID,
        created_by: uuid.UUID | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> Job:
        """Create and enqueue a new background job."""
        return await self.dispatcher.dispatch(
            db=db,
            organization_id=organization_id,
            job_type=request.job_type.value,
            payload=request.payload,
            priority=request.priority.value,
            idempotency_key=request.idempotency_key,
            max_attempts=request.max_attempts,
            created_by=created_by,
            trace_id=trace_id,
            request_id=request_id,
        )

    async def get_job(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Job:
        """Retrieve a specific job verifying tenant isolation."""
        stmt = select(Job).where(Job.id == job_id, Job.organization_id == organization_id)
        job = (await db.execute(stmt)).scalar_one_or_none()

        if not job:
            raise JobNotFoundError(job_id)

        JobSecurityPolicy.assert_tenant_access(organization_id, job)
        return job

    async def list_jobs(
        self,
        db: AsyncSession,
        organization_id: uuid.UUID,
        status: str | None = None,
        job_type: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> JobListResponse:
        """List jobs with filtering and pagination."""
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        offset = (page - 1) * page_size

        query = select(Job).where(Job.organization_id == organization_id)
        count_query = select(func.count(Job.id)).where(Job.organization_id == organization_id)

        if status:
            query = query.where(Job.status == status)
            count_query = count_query.where(Job.status == status)

        if job_type:
            query = query.where(Job.job_type == job_type)
            count_query = count_query.where(Job.job_type == job_type)

        if created_after:
            query = query.where(Job.created_at >= created_after)
            count_query = count_query.where(Job.created_at >= created_after)

        if created_before:
            query = query.where(Job.created_at <= created_before)
            count_query = count_query.where(Job.created_at <= created_before)

        total = (await db.execute(count_query)).scalar() or 0
        pages = (total + page_size - 1) // page_size if total > 0 else 1

        query = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size)
        jobs = list((await db.execute(query)).scalars().all())

        return JobListResponse(
            items=[JobResponse.model_validate(j) for j in jobs],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def cancel_job(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        reason: str = "Cancelled by user",
    ) -> Job:
        """Cancel a pending, running, or retry_scheduled job."""
        job = await self.get_job(db, job_id, organization_id)
        return await JobCancellationManager.request_cancellation(
            db=db,
            job_id=job.id,
            organization_id=organization_id,
            reason=reason,
        )

    async def retry_job(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        force: bool = False,
    ) -> Job:
        """Manually retry a failed or dead-lettered job."""
        job = await self.get_job(db, job_id, organization_id)

        if job.status not in (JobStatus.FAILED.value, JobStatus.DEAD_LETTER.value) and not force:
            raise InvalidJobStateTransitionError(
                job.status,
                JobStatus.QUEUED.value,
            )

        # Reset state and re-queue
        updated = await JobLifecycleManager.mark_queued(db, job)
        await self.queue.enqueue(
            job_id=updated.id,
            job_type=updated.job_type,
            priority=updated.priority,
        )

        logger.info(
            "Job manually retried and enqueued",
            job_id=str(updated.id),
            job_type=updated.job_type,
            organization_id=str(organization_id),
        )

        return updated

    async def get_health(self, db: AsyncSession) -> JobHealthResponse:
        """Get health status of jobs and worker subsystem."""
        return await WorkerHealthMonitor.get_health_status(
            db=db,
            redis_client=self.redis_client,
            queue=self.queue,
        )

"""Job dispatcher responsible for validation, idempotency, DB persistence, and queueing."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.jobs.config import job_config
from app.jobs.exceptions import (
    JobError,
    JobQueueFullError,
)
from app.jobs.idempotency import JobIdempotencyManager
from app.jobs.models import Job
from app.jobs.policies import JobSecurityPolicy
from app.jobs.queue import JobQueue
from app.jobs.schemas import JobPriority, JobStatus

logger = get_logger("jobs.dispatcher")


class JobDispatcher:
    """Validates, deduplicates, persists and dispatches jobs to the background queue."""

    def __init__(self, queue: JobQueue) -> None:
        self.queue = queue

    async def dispatch(
        self,
        db: AsyncSession,
        *,
        organization_id: uuid.UUID,
        job_type: str,
        payload: dict[str, Any],
        priority: str = JobPriority.NORMAL.value,
        idempotency_key: str | None = None,
        max_attempts: int | None = None,
        created_by: uuid.UUID | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> Job:
        """Enqueue a new job with idempotency and durability guarantees."""
        # 1. Validate payload security and size limits
        JobSecurityPolicy.validate_payload(payload)

        # 2. Check backpressure
        current_depth = await self.queue.get_depth()
        if current_depth >= job_config.MAX_QUEUE_DEPTH:
            raise JobQueueFullError(current_depth, job_config.MAX_QUEUE_DEPTH)

        # 3. Canonical hash and idempotency check
        payload_hash = JobIdempotencyManager.compute_payload_hash(payload)
        if idempotency_key:
            # Check for existing job
            # Since AsyncSession is used, we execute query asynchronously
            from sqlalchemy import select

            stmt = (
                select(Job)
                .where(
                    Job.organization_id == organization_id,
                    Job.idempotency_key == idempotency_key,
                )
                .limit(1)
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()

            if existing is not None:
                if existing.deduplication_hash != payload_hash:
                    from app.jobs.exceptions import JobIdempotencyConflictError

                    raise JobIdempotencyConflictError(idempotency_key)
                logger.info(
                    "Replaying existing idempotent job",
                    job_id=str(existing.id),
                    idempotency_key=idempotency_key,
                )
                return existing

        # 4. Create and persist durable Job record in PostgreSQL
        attempts_limit = max_attempts or job_config.DEFAULT_MAX_ATTEMPTS
        new_job = Job(
            organization_id=organization_id,
            created_by=created_by,
            job_type=job_type,
            status=JobStatus.QUEUED.value,
            priority=priority,
            payload=payload,
            attempt=0,
            max_attempts=attempts_limit,
            idempotency_key=idempotency_key,
            deduplication_hash=payload_hash,
            trace_id=trace_id,
            request_id=request_id,
        )

        db.add(new_job)
        await db.commit()
        await db.refresh(new_job)

        # 5. Push to queue
        try:
            await self.queue.enqueue(
                job_id=new_job.id,
                job_type=new_job.job_type,
                priority=new_job.priority,
            )
        except Exception as queue_exc:
            # Job remains safe and durable in DB with status=queued
            logger.error(
                "Failed to push job to broker queue after DB persistence",
                job_id=str(new_job.id),
                error=str(queue_exc),
            )
            # Re-raise so client is informed, but DB state is not corrupted
            raise JobError(
                f"Job created in database but failed to enqueue to broker: {queue_exc}",
                code="JOB_ENQUEUE_FAILED",
                retryable=True,
            ) from queue_exc

        logger.info(
            "Job successfully dispatched",
            job_id=str(new_job.id),
            job_type=new_job.job_type,
            priority=new_job.priority,
            organization_id=str(organization_id),
        )

        from app.jobs.metrics import JobMetrics

        JobMetrics.record_job_dispatched(new_job.job_type, new_job.priority)

        return new_job

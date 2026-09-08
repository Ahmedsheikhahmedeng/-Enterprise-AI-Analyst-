"""Job cancellation manager and checkpoint safety enforcement."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.jobs.exceptions import (
    InvalidJobStateTransitionError,
    JobCancellationError,
    JobNotFoundError,
)
from app.jobs.lifecycle import JobLifecycleManager
from app.jobs.models import Job
from app.jobs.schemas import JobStatus

logger = get_logger("jobs.cancellation")


class JobCancellationManager:
    """Handles cancellation requests and checkpoint verification."""

    # Set of in-flight cancelled job IDs for fast checkpoint lookup
    _active_cancellations: set[uuid.UUID] = set()

    @classmethod
    def register_cancellation(cls, job_id: uuid.UUID) -> None:
        """Register job_id as actively cancelled for memory-speed checkpoint checks."""
        cls._active_cancellations.add(job_id)

    @classmethod
    def unregister_cancellation(cls, job_id: uuid.UUID) -> None:
        """Clear job_id from cancellation tracking after worker cleans up."""
        cls._active_cancellations.discard(job_id)

    @classmethod
    def is_cancelled(cls, job_id: uuid.UUID) -> bool:
        """Check if job has been flagged for cancellation."""
        return job_id in cls._active_cancellations

    @classmethod
    def check_checkpoint(cls, job_id: uuid.UUID) -> None:
        """Helper to check cancellation and immediately abort if cancelled."""
        if cls.is_cancelled(job_id):
            raise JobCancellationError(job_id, "Aborted at safe checkpoint")

    @classmethod
    async def request_cancellation(
        cls,
        db: AsyncSession,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        reason: str = "Cancelled by user",
    ) -> Job:
        """Cancel a job if it is in queued, running, or retry_scheduled state."""
        stmt = select(Job).where(Job.id == job_id, Job.organization_id == organization_id)
        job = (await db.execute(stmt)).scalar_one_or_none()

        if not job:
            raise JobNotFoundError(job_id)

        if job.status in (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.DEAD_LETTER.value,
        ):
            raise InvalidJobStateTransitionError(job.status, JobStatus.CANCELLED.value)

        if job.status == JobStatus.CANCELLED.value:
            return job

        # Flag for running workers
        cls.register_cancellation(job.id)

        # Update database record
        updated_job = await JobLifecycleManager.mark_cancelled(db=db, job=job, reason=reason)

        logger.info(
            "Job cancelled",
            job_id=str(job_id),
            organization_id=str(organization_id),
            reason=reason,
        )

        return updated_job

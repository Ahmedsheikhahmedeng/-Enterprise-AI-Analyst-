"""Job state machine enforcement and lifecycle transition manager."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.exceptions import InvalidJobStateTransitionError
from app.jobs.models import Job
from app.jobs.schemas import JobStatus


class JobLifecycleManager:
    """Enforces strict state transitions and updates Job persistent records."""

    # Explicit allowed transition graph
    ALLOWED_TRANSITIONS: dict[str, set[str]] = {
        JobStatus.QUEUED.value: {
            JobStatus.RUNNING.value,
            JobStatus.CANCELLED.value,
        },
        JobStatus.RUNNING.value: {
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.RETRY_SCHEDULED.value,
            JobStatus.CANCELLED.value,
        },
        JobStatus.RETRY_SCHEDULED.value: {
            JobStatus.QUEUED.value,
            JobStatus.RUNNING.value,
            JobStatus.CANCELLED.value,
        },
        JobStatus.FAILED.value: {
            JobStatus.DEAD_LETTER.value,
            JobStatus.QUEUED.value,  # Manual retry recovery
        },
        JobStatus.DEAD_LETTER.value: {
            JobStatus.QUEUED.value,  # Manual retry recovery
        },
        JobStatus.COMPLETED.value: set(),  # Terminal state
        JobStatus.CANCELLED.value: set(),  # Terminal state
    }

    @classmethod
    def validate_transition(cls, current_status: str, target_status: str) -> None:
        """Validate whether the transition from current_status to target_status is legal."""
        allowed = cls.ALLOWED_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise InvalidJobStateTransitionError(current_status, target_status)

    @classmethod
    async def mark_running(cls, db: AsyncSession, job: Job, worker_id: str) -> Job:
        """Transition job from queued to running."""
        cls.validate_transition(job.status, JobStatus.RUNNING.value)
        job.status = JobStatus.RUNNING.value
        job.worker_id = worker_id
        job.started_at = datetime.now(UTC)
        job.attempt += 1
        await db.commit()
        await db.refresh(job)
        return job

    @classmethod
    async def mark_completed(cls, db: AsyncSession, job: Job, result: dict[str, Any]) -> Job:
        """Transition job from running to completed."""
        cls.validate_transition(job.status, JobStatus.COMPLETED.value)
        job.status = JobStatus.COMPLETED.value
        job.completed_at = datetime.now(UTC)
        job.result = result
        job.progress = 1.0
        job.progress_message = "Completed successfully"
        job.error_code = None
        job.error_message = None
        await db.commit()
        await db.refresh(job)
        return job

    @classmethod
    async def mark_retry_scheduled(
        cls,
        db: AsyncSession,
        job: Job,
        next_retry_at: datetime,
        error_code: str,
        error_message: str,
    ) -> Job:
        """Transition job from running to retry_scheduled."""
        cls.validate_transition(job.status, JobStatus.RETRY_SCHEDULED.value)
        job.status = JobStatus.RETRY_SCHEDULED.value
        job.next_retry_at = next_retry_at
        job.error_code = error_code
        job.error_message = error_message
        await db.commit()
        await db.refresh(job)
        return job

    @classmethod
    async def mark_failed(
        cls,
        db: AsyncSession,
        job: Job,
        error_code: str,
        error_message: str,
    ) -> Job:
        """Transition job from running to failed."""
        cls.validate_transition(job.status, JobStatus.FAILED.value)
        job.status = JobStatus.FAILED.value
        job.completed_at = datetime.now(UTC)
        job.error_code = error_code
        job.error_message = error_message
        await db.commit()
        await db.refresh(job)
        return job

    @classmethod
    async def mark_dead_letter(
        cls,
        db: AsyncSession,
        job: Job,
        error_code: str,
        error_message: str,
    ) -> Job:
        """Transition job from running or failed to dead_letter."""
        # Allow running -> failed -> dead_letter or direct to dead_letter if classified fatal
        if job.status == JobStatus.RUNNING.value:
            job.status = JobStatus.FAILED.value
        cls.validate_transition(job.status, JobStatus.DEAD_LETTER.value)
        job.status = JobStatus.DEAD_LETTER.value
        job.completed_at = datetime.now(UTC)
        job.error_code = error_code
        job.error_message = error_message
        await db.commit()
        await db.refresh(job)
        return job

    @classmethod
    async def mark_cancelled(
        cls,
        db: AsyncSession,
        job: Job,
        reason: str = "Cancelled by user",
    ) -> Job:
        """Transition job to cancelled from queued, running, or retry_scheduled."""
        cls.validate_transition(job.status, JobStatus.CANCELLED.value)
        job.status = JobStatus.CANCELLED.value
        job.cancelled_at = datetime.now(UTC)
        job.completed_at = datetime.now(UTC)
        job.error_code = "JOB_CANCELLED"
        job.error_message = reason
        await db.commit()
        await db.refresh(job)
        return job

    @classmethod
    async def mark_queued(cls, db: AsyncSession, job: Job) -> Job:
        """Re-enqueue job from retry_scheduled, or reset for manual retry."""
        cls.validate_transition(job.status, JobStatus.QUEUED.value)
        job.status = JobStatus.QUEUED.value
        job.started_at = None
        job.completed_at = None
        job.cancelled_at = None
        job.next_retry_at = None
        job.worker_id = None
        await db.commit()
        await db.refresh(job)
        return job

    @classmethod
    async def update_progress(
        cls,
        db: AsyncSession,
        job: Job,
        progress: float,
        message: str | None = None,
    ) -> None:
        """Update job execution progress without changing status."""
        job.progress = max(0.0, min(1.0, progress))
        if message:
            job.progress_message = message[:255]
        await db.commit()

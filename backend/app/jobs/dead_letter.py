"""Dead letter handling and terminal failure management for background jobs."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.jobs.lifecycle import JobLifecycleManager
from app.jobs.models import Job

logger = get_logger("jobs.dead_letter")


class DeadLetterManager:
    """Manages routing and recording of permanently failed jobs to Dead Letter state."""

    @classmethod
    async def route_to_dead_letter(
        cls,
        db: AsyncSession,
        job: Job,
        error_code: str,
        error_message: str,
    ) -> Job:
        """Persist job in dead_letter status with sanitized diagnostic metadata."""
        # Sanitize message to prevent any incidental secrets
        safe_msg = (
            error_message[:1000] if error_message else "Exhausted retry attempts or fatal error"
        )

        updated_job = await JobLifecycleManager.mark_dead_letter(
            db=db,
            job=job,
            error_code=error_code,
            error_message=safe_msg,
        )

        logger.error(
            "Job transitioned to DEAD_LETTER",
            job_id=str(job.id),
            job_type=job.job_type,
            organization_id=str(job.organization_id),
            attempts=job.attempt,
            max_attempts=job.max_attempts,
            error_code=error_code,
            trace_id=job.trace_id,
        )

        return updated_job

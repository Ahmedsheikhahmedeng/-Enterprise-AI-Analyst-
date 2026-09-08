"""Worker health monitoring, heartbeats, and stuck job detection."""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.jobs.config import job_config
from app.jobs.models import Job
from app.jobs.queue import JobQueue
from app.jobs.schemas import JobHealthResponse, JobStatus

logger = get_logger("jobs.health")


class WorkerHealthMonitor:
    """Monitors worker heartbeats, queue health, and flags stuck running jobs."""

    HEARTBEAT_PREFIX = "jobs:worker:"

    @classmethod
    def heartbeat_key(cls, worker_id: str) -> str:
        return f"{cls.HEARTBEAT_PREFIX}{worker_id}:heartbeat"

    @classmethod
    async def record_heartbeat(
        cls,
        redis_client: Redis | None,
        worker_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record worker liveness heartbeat in Redis with TTL."""
        if redis_client is None:
            return
        key = cls.heartbeat_key(worker_id)
        now_ts = str(time.time())
        try:
            await redis_client.set(key, now_ts, ex=job_config.WORKER_HEARTBEAT_TTL_SECONDS)
        except Exception as exc:
            logger.warning("Failed to record worker heartbeat", worker_id=worker_id, error=str(exc))

    @classmethod
    async def get_active_workers(cls, redis_client: Redis | None) -> list[str]:
        """List active worker IDs based on valid heartbeat keys."""
        if redis_client is None:
            return []
        try:
            keys = await redis_client.keys(f"{cls.HEARTBEAT_PREFIX}*:heartbeat")
            workers: list[str] = []
            for k in keys:
                # Key format: jobs:worker:{worker_id}:heartbeat
                parts = str(k).split(":")
                if len(parts) >= 4:
                    workers.append(parts[2])
            return workers
        except Exception as exc:
            logger.warning("Failed to retrieve active worker keys", error=str(exc))
            return []

    @classmethod
    async def detect_stuck_jobs(
        cls,
        db: AsyncSession,
        stuck_timeout_seconds: float = job_config.STUCK_JOB_TIMEOUT_SECONDS,
    ) -> list[Job]:
        """Detect jobs that have been in RUNNING status longer than max_runtime without completion."""
        cutoff = datetime.now(UTC) - timedelta(seconds=stuck_timeout_seconds)
        stmt = select(Job).where(
            Job.status == JobStatus.RUNNING.value,
            Job.started_at.is_not(None),
            Job.started_at < cutoff,
        )
        result = await db.execute(stmt)
        stuck_jobs = list(result.scalars().all())

        if stuck_jobs:
            logger.warning(
                "Detected stuck running jobs",
                count=len(stuck_jobs),
                job_ids=[str(j.id) for j in stuck_jobs],
            )
        return stuck_jobs

    @classmethod
    async def get_health_status(
        cls,
        db: AsyncSession,
        redis_client: Redis | None,
        queue: JobQueue,
    ) -> JobHealthResponse:
        """Generate comprehensive health report for jobs & worker subsystem."""
        redis_reachable = False
        active_workers = 0
        if redis_client is not None:
            try:
                pong = await redis_client.ping()
                redis_reachable = bool(pong)
                workers = await cls.get_active_workers(redis_client)
                active_workers = len(workers)
            except Exception:
                redis_reachable = False

        depths = await queue.get_all_depths()
        stuck = await cls.detect_stuck_jobs(db)

        status = "healthy"
        if not redis_reachable and redis_client is not None:
            status = "degraded"
        if len(stuck) > 10:
            status = "degraded"

        return JobHealthResponse(
            status=status,
            redis_reachable=redis_reachable,
            queue_depths=depths,
            active_workers=active_workers,
            stuck_jobs=len(stuck),
        )

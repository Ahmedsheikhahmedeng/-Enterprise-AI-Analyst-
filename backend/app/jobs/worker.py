"""Distributed Background Worker implementing polling, concurrency, heartbeats and graceful shutdown."""

import asyncio
import os
import socket
import time
import uuid
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.jobs.cancellation import JobCancellationManager
from app.jobs.config import job_config
from app.jobs.context import JobContext
from app.jobs.dead_letter import DeadLetterManager
from app.jobs.exceptions import JobCancellationError
from app.jobs.health import WorkerHealthMonitor
from app.jobs.lifecycle import JobLifecycleManager
from app.jobs.models import Job
from app.jobs.queue import JobQueue
from app.jobs.registry import TaskRegistry, task_registry
from app.jobs.retry import RetryClassifier, RetryPolicy
from app.jobs.schemas import JobStatus
from app.workers.ingestion import get_worker_session_factory

logger = get_logger("jobs.worker")


class Worker:
    """Production background worker for reliable, concurrency-controlled job processing."""

    def __init__(
        self,
        queue: JobQueue,
        worker_id: str | None = None,
        concurrency: int = job_config.WORKER_CONCURRENCY,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        redis_client: Redis | None = None,
        registry: TaskRegistry | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        hostname = socket.gethostname()
        pid = os.getpid()
        rand = uuid.uuid4().hex[:6]
        self.worker_id = worker_id or f"{hostname}-{pid}-{rand}"
        self.queue = queue
        self.concurrency = concurrency
        self.session_factory = session_factory or get_worker_session_factory()
        self.redis_client = redis_client
        self.registry = registry or task_registry
        self.retry_policy = retry_policy or RetryPolicy()

        self._running = False
        self._shutdown_event = asyncio.Event()
        self._semaphore = asyncio.Semaphore(concurrency)
        self._active_tasks: set[asyncio.Task[Any]] = set()

        # Per-type concurrency limits
        self._type_semaphores: dict[str, asyncio.Semaphore] = {
            j_type: asyncio.Semaphore(limit)
            for j_type, limit in job_config.MAX_CONCURRENT_PER_TYPE.items()
        }
        self._heartbeat_task: asyncio.Task[None] | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def busy_count(self) -> int:
        return len(self._active_tasks)

    async def start(self) -> None:
        """Start worker polling loop and heartbeat."""
        self._running = True
        self._shutdown_event.clear()
        logger.info("Worker started", worker_id=self.worker_id, concurrency=self.concurrency)

        # Start heartbeat background loop
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat reporter."""
        while self._running:
            try:
                await WorkerHealthMonitor.record_heartbeat(self.redis_client, self.worker_id)
            except Exception as exc:
                logger.warning("Worker heartbeat failed", worker_id=self.worker_id, error=str(exc))
            try:
                await asyncio.sleep(job_config.WORKER_HEARTBEAT_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break

    async def run_until_shutdown(self) -> None:
        """Main worker execution loop processing jobs until shutdown is signaled."""
        await self.start()
        while self.is_running:
            try:
                # Wait for available concurrency slot
                await self._semaphore.acquire()

                if self._shutdown_event.is_set():
                    self._semaphore.release()
                    break

                job_id = await self.queue.dequeue(worker_id=self.worker_id, timeout=1.0)
                if not job_id:
                    self._semaphore.release()
                    await asyncio.sleep(0.05)
                    continue

                # Spawn job execution as tracked background task
                task = asyncio.create_task(self._execute_job_wrapper(job_id))
                self._active_tasks.add(task)

                def _cleanup(t: asyncio.Task[Any]) -> None:
                    self._active_tasks.discard(t)
                    self._semaphore.release()

                task.add_done_callback(_cleanup)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "Unexpected error in worker loop", worker_id=self.worker_id, error=str(exc)
                )
                await asyncio.sleep(0.5)

    async def process_one(self, timeout: float = 1.0) -> bool:
        """Process at most one job synchronously (useful for tests and manual dispatch)."""
        job_id = await self.queue.dequeue(worker_id=self.worker_id, timeout=timeout)
        if not job_id:
            return False
        await self._execute_job(job_id)
        return True

    async def _execute_job_wrapper(self, job_id: uuid.UUID) -> None:
        """Safe wrapper around _execute_job for task management."""
        try:
            await self._execute_job(job_id)
        except Exception as exc:
            logger.error(
                "Unhandled exception during job execution", job_id=str(job_id), error=str(exc)
            )

    async def _execute_job(self, job_id: uuid.UUID) -> None:
        """Fetch job, transition to running, dispatch to handler, and handle completion/retry."""
        async with self.session_factory() as session:
            stmt = select(Job).where(Job.id == job_id)
            job = (await session.execute(stmt)).scalar_one_or_none()

            if not job:
                logger.warning("Dequeued job not found in database", job_id=str(job_id))
                await self.queue.ack(job_id)
                return

            # Check if cancelled before execution
            if job.status == JobStatus.CANCELLED.value or JobCancellationManager.is_cancelled(
                job.id
            ):
                logger.info("Job was cancelled before execution started", job_id=str(job.id))
                await self.queue.ack(job_id)
                return

            # Respect per-type concurrency if configured
            type_sem = self._type_semaphores.get(job.job_type)
            if type_sem:
                await type_sem.acquire()

            try:
                # Transition to running
                await JobLifecycleManager.mark_running(session, job, self.worker_id)

                # Build context
                def _cancellation_check() -> bool:
                    return JobCancellationManager.is_cancelled(job.id)

                def _progress_reporter(prog: float, msg: str | None) -> None:
                    # Async schedule or direct update
                    asyncio.create_task(self._update_job_progress(job.id, prog, msg))

                context = JobContext(
                    job_id=job.id,
                    organization_id=job.organization_id,
                    job_type=job.job_type,
                    attempt=job.attempt,
                    max_attempts=job.max_attempts,
                    created_by=job.created_by,
                    trace_id=job.trace_id,
                    request_id=job.request_id,
                    worker_id=self.worker_id,
                    _cancellation_checker=_cancellation_check,
                    _progress_reporter=_progress_reporter,
                )

                # Resolve task handler
                handler = self.registry.get(job.job_type)

                logger.info(
                    "Executing job",
                    job_id=str(job.id),
                    job_type=job.job_type,
                    attempt=job.attempt,
                    organization_id=str(job.organization_id),
                )

                # Run handler
                start_time = time.monotonic()
                result = await handler.run(job.payload, context)
                duration_ms = (time.monotonic() - start_time) * 1000.0

                # Mark completed
                await JobLifecycleManager.mark_completed(session, job, result)
                await self.queue.ack(job.id)

                from app.jobs.metrics import JobMetrics

                JobMetrics.record_job_completed(job.job_type, duration_ms, job.attempt)

                logger.info(
                    "Job completed successfully",
                    job_id=str(job.id),
                    job_type=job.job_type,
                    duration_ms=round(duration_ms, 2),
                )

            except JobCancellationError as cancel_exc:
                logger.warning(
                    "Job cancelled during execution", job_id=str(job.id), reason=str(cancel_exc)
                )
                await JobLifecycleManager.mark_cancelled(session, job, str(cancel_exc))
                await self.queue.ack(job.id)
                from app.jobs.metrics import JobMetrics

                JobMetrics.record_job_cancelled(job.job_type)

            except Exception as exc:
                error_code = getattr(exc, "code", type(exc).__name__)
                error_message = str(exc)
                is_retryable = RetryClassifier.is_retryable(exc)

                logger.warning(
                    "Job execution encountered error",
                    job_id=str(job.id),
                    job_type=job.job_type,
                    attempt=job.attempt,
                    max_attempts=job.max_attempts,
                    retryable=is_retryable,
                    error=error_message,
                )

                from app.jobs.metrics import JobMetrics

                if is_retryable and job.attempt < job.max_attempts:
                    next_retry_at = self.retry_policy.compute_next_retry_at(job.attempt)
                    delay = (
                        max(0.0, (next_retry_at - job.started_at).total_seconds())
                        if job.started_at
                        else 1.0
                    )
                    await JobLifecycleManager.mark_retry_scheduled(
                        session,
                        job,
                        next_retry_at=next_retry_at,
                        error_code=error_code,
                        error_message=error_message,
                    )
                    await self.queue.nack(job.id, delay_seconds=delay)
                    JobMetrics.record_job_retry_scheduled(job.job_type)
                else:
                    # Move to Dead Letter
                    await DeadLetterManager.route_to_dead_letter(
                        session,
                        job,
                        error_code=error_code,
                        error_message=error_message,
                    )
                    await self.queue.ack(job.id)
                    JobMetrics.record_job_dead_lettered(job.job_type)

            finally:
                if type_sem:
                    type_sem.release()
                JobCancellationManager.unregister_cancellation(job.id)

    async def _update_job_progress(self, job_id: uuid.UUID, prog: float, msg: str | None) -> None:
        """Asynchronously update progress in a separate session."""
        try:
            async with self.session_factory() as session:
                stmt = select(Job).where(Job.id == job_id)
                job = (await session.execute(stmt)).scalar_one_or_none()
                if job and job.status == JobStatus.RUNNING.value:
                    await JobLifecycleManager.update_progress(session, job, prog, msg)
        except Exception:
            pass

    async def shutdown(self, timeout: float = job_config.WORKER_SHUTDOWN_TIMEOUT_SECONDS) -> None:
        """Gracefully stop worker: cancel polling, wait for in-flight tasks, and release resources."""
        logger.info(
            "Worker shutting down gracefully",
            worker_id=self.worker_id,
            active_tasks=len(self._active_tasks),
        )
        self._running = False
        self._shutdown_event.set()

        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        if self._active_tasks:
            logger.info(
                f"Waiting up to {timeout}s for {len(self._active_tasks)} active jobs to complete..."
            )
            done, pending = await asyncio.wait(self._active_tasks, timeout=timeout)
            if pending:
                logger.warning(
                    f"{len(pending)} jobs did not complete in time during shutdown, cancelling..."
                )
                for t in pending:
                    t.cancel()

        logger.info("Worker shutdown complete", worker_id=self.worker_id)


async def main() -> None:
    """Entrypoint for standalone background worker process with graceful signal handling."""
    import contextlib
    import signal

    from app.core.config import get_settings
    from app.db.postgres import create_database_engine, create_session_factory
    from app.db.redis import create_redis_client
    from app.jobs.queue import RedisJobQueue

    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    redis_client = create_redis_client(settings)
    queue = RedisJobQueue(redis_client)

    worker = Worker(
        queue=queue,
        session_factory=session_factory,
        redis_client=redis_client,
        concurrency=job_config.WORKER_CONCURRENCY,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(worker.shutdown()),
            )

    logger.info("Worker process starting up", worker_id=worker.worker_id)
    try:
        await worker.run_until_shutdown()
    finally:
        await worker.shutdown()
        with contextlib.suppress(Exception):
            await redis_client.aclose()
        with contextlib.suppress(Exception):
            await engine.dispose()
        logger.info("Worker process exited cleanly")


if __name__ == "__main__":
    asyncio.run(main())

"""Background task scheduler with bounded concurrency for heavy evaluation workloads."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


class EvaluationTaskScheduler:
    """Manages asynchronous background execution of benchmark evaluations with strict concurrency bounds."""

    def __init__(self, max_concurrent_runs: int = 4) -> None:
        self.semaphore = asyncio.Semaphore(max_concurrent_runs)
        self._active_tasks: dict[str, asyncio.Task[Any]] = {}

    async def schedule(
        self,
        task_id: str,
        coro_fn: Callable[[], Awaitable[Any]],
        on_complete: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> asyncio.Task[Any]:
        """Schedules a coroutine function in the background under bounded semaphore concurrency."""

        async def _worker() -> Any:
            async with self.semaphore:
                try:
                    logger.info("Starting background evaluation task %s", task_id)
                    result = await coro_fn()
                    if on_complete:
                        on_complete(result)
                    return result
                except Exception as exc:
                    logger.exception(
                        "Background evaluation task %s encountered failure: %s", task_id, exc
                    )
                    if on_error:
                        on_error(exc)
                    raise
                finally:
                    self._active_tasks.pop(task_id, None)

        task = asyncio.create_task(_worker(), name=f"eval-task-{task_id}")
        self._active_tasks[task_id] = task
        return task

    def cancel_task(self, task_id: str) -> bool:
        """Cancels an active background evaluation task if running."""
        task = self._active_tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    @property
    def active_task_count(self) -> int:
        """Returns the number of currently scheduled/running background evaluation tasks."""
        return len(self._active_tasks)

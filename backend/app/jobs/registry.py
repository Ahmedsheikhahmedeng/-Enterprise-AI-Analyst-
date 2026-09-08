"""Decoupled task handler registry mapping job types to execution handlers."""

from collections.abc import Callable
from typing import Any, Protocol

from app.jobs.context import JobContext
from app.jobs.exceptions import JobError


class TaskHandler(Protocol):
    """Protocol defining the task handler execution signature."""

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        """Execute task logic idempotently, checking context.is_cancelled() periodically."""
        ...


class TaskRegistry:
    """Registry mapping job_type strings to TaskHandler classes or factories."""

    def __init__(self) -> None:
        self._handlers: dict[str, type[TaskHandler] | Callable[[], TaskHandler] | TaskHandler] = {}

    def register(
        self,
        job_type: str,
        handler: type[TaskHandler] | Callable[[], TaskHandler] | TaskHandler,
    ) -> None:
        """Register a handler for a job type."""
        self._handlers[job_type] = handler

    def get(self, job_type: str) -> TaskHandler:
        """Resolve and instantiate a handler for the given job type."""
        if job_type not in self._handlers:
            raise JobError(
                f"No task handler registered for job type '{job_type}'", code="TASK_NOT_REGISTERED"
            )

        handler_or_factory = self._handlers[job_type]
        if (
            isinstance(handler_or_factory, type)
            or callable(handler_or_factory)
            and not hasattr(handler_or_factory, "run")
        ):
            return handler_or_factory()
        return handler_or_factory

    def list_types(self) -> list[str]:
        """List all currently registered job types."""
        return sorted(self._handlers.keys())


# Global registry singleton
task_registry = TaskRegistry()

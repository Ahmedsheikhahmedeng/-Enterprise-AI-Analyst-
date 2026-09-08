"""Task handler for executing agent sessions asynchronously within worker pools."""

import uuid
from typing import Any

from app.agents.service import AgentService
from app.jobs.context import JobContext
from app.jobs.exceptions import JobCancellationError, NonRetryableJobError
from app.rbac.catalog import DEFAULT_ROLE_PERMISSIONS, ROLE_ADMIN
from app.workers.ingestion import get_worker_session_factory


class AgentExecutionTask:
    """Executes long-running AgentSession runs inside background workers."""

    def __init__(self, agent_service: AgentService | None = None) -> None:
        self.agent_service = agent_service or AgentService()
        self.session_factory = get_worker_session_factory()

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        session_id_str = payload.get("session_id")
        if not session_id_str:
            raise NonRetryableJobError("Missing required 'session_id' in agent_execution payload")

        try:
            session_id = uuid.UUID(str(session_id_str))
        except ValueError as exc:
            raise NonRetryableJobError(f"Invalid session_id format: {session_id_str}") from exc

        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        user_perms = set(DEFAULT_ROLE_PERMISSIONS[ROLE_ADMIN])

        async with self.session_factory() as session:
            res = await self.agent_service.start_session(
                db_session=session,
                session_id=session_id,
                organization_id=context.organization_id,
                user_permissions=user_perms,
                user_id=context.created_by,
            )
            return res.model_dump(mode="json")

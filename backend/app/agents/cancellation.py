"""Cooperative cancellation checking and termination coordination."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.exceptions import AgentCancellationError
from app.agents.models import AgentSession
from app.agents.schemas import AgentStatus


class AgentCancellationManager:
    """Provides cooperative cancellation checks throughout step and tool execution cycles."""

    @staticmethod
    async def check_cancelled(db_session: AsyncSession, session_id: UUID) -> None:
        """Poll session status; raises AgentCancellationError if marked cancelled."""
        stmt = select(AgentSession.status).where(AgentSession.id == session_id)
        res = await db_session.execute(stmt)
        status = res.scalar_one_or_none()
        if status == AgentStatus.CANCELLED.value:
            raise AgentCancellationError(session_id)

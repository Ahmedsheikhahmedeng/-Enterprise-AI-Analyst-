"""Immutable checkpoint persistence and retrieval for crash recovery and resume."""

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import AgentCheckpoint


class CheckpointManager:
    """Manages creation and retrieval of deterministic execution checkpoints."""

    @staticmethod
    def compute_input_hash(tool_input: dict[str, Any]) -> str:
        """Compute SHA256 hash of normalized tool input payload."""
        serialized = json.dumps(tool_input, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def save_checkpoint(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        step_id: UUID,
        organization_id: UUID,
        status: str,
        tool_name: str,
        tool_input: dict[str, Any],
        evidence_ids: list[str],
        state_snapshot: dict[str, Any],
        result_reference: str | None = None,
    ) -> AgentCheckpoint:
        """Persist a point-in-time checkpoint for a completed step."""
        tool_input_hash = self.compute_input_hash(tool_input)
        cp = AgentCheckpoint(
            session_id=session_id,
            step_id=step_id,
            organization_id=organization_id,
            status=status,
            tool_name=tool_name,
            tool_input_hash=tool_input_hash,
            tool_result_reference=result_reference,
            evidence_ids=evidence_ids,
            state_snapshot=state_snapshot,
        )
        db_session.add(cp)
        await db_session.flush()
        return cp

    async def get_latest_checkpoint(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        organization_id: UUID,
    ) -> AgentCheckpoint | None:
        """Fetch latest valid checkpoint for session within tenant boundary."""
        stmt = (
            select(AgentCheckpoint)
            .where(
                AgentCheckpoint.session_id == session_id,
                AgentCheckpoint.organization_id == organization_id,
            )
            .order_by(AgentCheckpoint.created_at.desc())
            .limit(1)
        )
        res = await db_session.execute(stmt)
        return res.scalars().first()

    async def find_matching_checkpoint(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> AgentCheckpoint | None:
        """Locate existing successful checkpoint matching tool and input hash."""
        input_hash = self.compute_input_hash(tool_input)
        stmt = (
            select(AgentCheckpoint)
            .where(
                AgentCheckpoint.session_id == session_id,
                AgentCheckpoint.tool_name == tool_name,
                AgentCheckpoint.tool_input_hash == input_hash,
                AgentCheckpoint.status == "completed",
            )
            .order_by(AgentCheckpoint.created_at.desc())
            .limit(1)
        )
        res = await db_session.execute(stmt)
        return res.scalars().first()

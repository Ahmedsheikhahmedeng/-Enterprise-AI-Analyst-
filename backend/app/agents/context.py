"""Execution context passed into tool invocations and step orchestrations."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class AgentExecutionContext:
    """Carried context during tool execution enforcing tenancy, correlation, and budgets."""

    organization_id: UUID
    session_id: UUID
    step_id: UUID
    db_session: AsyncSession
    user_id: UUID | None = None
    trace_id: str | None = None
    request_id: str | None = None
    deadline: datetime | None = None
    step_number: int = 1
    metadata: dict[str, str] = field(default_factory=dict)

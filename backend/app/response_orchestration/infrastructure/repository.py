"""Database repository for persisting orchestration executions and granular steps."""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.orchestration import (
    OrchestrationExecutionModel,
    OrchestrationStepModel,
)

logger = logging.getLogger(__name__)


class OrchestrationRepository:
    """Provides transactional persistence and retrieval for orchestration records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_execution(
        self,
        execution_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        query: str,
        mode: str = "AUTO",
        conversation_id: uuid.UUID | None = None,
    ) -> OrchestrationExecutionModel:
        """Create new execution session record."""
        record = OrchestrationExecutionModel(
            id=execution_id,
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
            query=query,
            mode=mode,
            status="RECEIVED",
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def record_step(
        self,
        execution_id: uuid.UUID,
        step_type: str,
        step_order: int,
        status: str = "completed",
        input_payload: dict[str, Any] | None = None,
        output_payload: dict[str, Any] | None = None,
        latency_ms: int = 0,
    ) -> OrchestrationStepModel:
        """Record atomic execution step trace."""
        step = OrchestrationStepModel(
            id=uuid.uuid4(),
            execution_id=execution_id,
            step_type=step_type,
            step_order=step_order,
            status=status,
            input_payload=input_payload,
            output_payload=output_payload,
            latency_ms=latency_ms,
        )
        self.session.add(step)
        await self.session.flush()
        return step

    async def get_execution(
        self,
        execution_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> OrchestrationExecutionModel | None:
        """Retrieve execution by ID enforcing tenant boundary."""
        stmt = (
            select(OrchestrationExecutionModel)
            .where(
                OrchestrationExecutionModel.id == execution_id,
                OrchestrationExecutionModel.organization_id == organization_id,
            )
            .options(selectinload(OrchestrationExecutionModel.steps))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

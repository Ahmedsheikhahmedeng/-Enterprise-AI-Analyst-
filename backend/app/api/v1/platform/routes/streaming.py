"""Server-Sent Events (SSE) Streaming and Event Replay Routes — TASK 34."""

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.platform.coordinator import (
    CoordinatorRegistry,
    get_coordinator_registry,
)
from app.api.v1.platform.dependencies import (
    check_rate_limit,
    get_correlation_ids,
)
from app.api.v1.platform.schemas.common import ApiResponse
from app.api.v1.platform.schemas.streaming import EventReplayResponse, StreamEvent
from app.core.logging import get_logger
from app.db.postgres import get_db_session
from app.rbac.catalog import PERM_ORCHESTRATION_READ
from app.response_orchestration.infrastructure.repository import OrchestrationRepository
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission

logger = get_logger("platform.routes.streaming")

streaming_router = APIRouter(tags=["Platform Streaming"])


@streaming_router.get(
    "/ask/{execution_id}/stream",
    response_class=StreamingResponse,
    summary="Real-time Server-Sent Events (SSE) execution stream",
    dependencies=[Depends(check_rate_limit("stream", limit_per_minute=120))],
)
async def stream_execution_events(
    execution_id: uuid.UUID,
    request: Request,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_READ))
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    registry: Annotated[CoordinatorRegistry, Depends(get_coordinator_registry)],
) -> StreamingResponse:
    """Stream live ordered reasoning events and final verified response via text/event-stream."""
    # 1. Verify execution existence and tenant ownership
    repo = OrchestrationRepository(session)
    exec_record = await repo.get_execution(execution_id, tenant_context.organization_id)
    if not exec_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found or tenant access denied.",
        )

    # 2. Retrieve or create coordinator
    coord = await registry.get_or_create(
        execution_id=execution_id,
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
    )

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for event in coord.subscribe():
                # Check client disconnect
                if await request.is_disconnected():
                    logger.info(
                        "Client disconnected from SSE stream", execution_id=str(execution_id)
                    )
                    break
                yield event.to_sse_format()
        except Exception as exc:
            logger.error(
                "Error during SSE streaming generator",
                execution_id=str(execution_id),
                error=str(exc),
            )
            err_event = StreamEvent(
                event="execution.failed",
                execution_id=str(execution_id),
                sequence=coord.current_sequence + 1,
                data={"error": "Streaming encountered an unrecoverable failure."},
            )
            yield err_event.to_sse_format()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@streaming_router.get(
    "/ask/{execution_id}/events",
    response_model=ApiResponse[EventReplayResponse],
    summary="Replay missed events after disconnect using sequence cursor",
    dependencies=[Depends(check_rate_limit("events", limit_per_minute=120))],
)
async def replay_execution_events(
    execution_id: uuid.UUID,
    request: Request,
    after_sequence: Annotated[
        int, Query(ge=0, description="Return events strictly after this sequence")
    ] = 0,
    tenant_context: Annotated[
        TenantContext, Depends(require_tenant_permission(PERM_ORCHESTRATION_READ))
    ] = None,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
    registry: Annotated[CoordinatorRegistry, Depends(get_coordinator_registry)] = None,  # type: ignore[assignment]
) -> ApiResponse[EventReplayResponse]:
    """Retrieve all ordered events with sequence > after_sequence to resume disconnected client state."""
    req_id, tr_id = get_correlation_ids(request)

    # 1. Verify existence & tenant boundary
    repo = OrchestrationRepository(session)
    record = await repo.get_execution(execution_id, tenant_context.organization_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found or tenant access denied.",
        )

    # 2. Try in-memory buffer first
    coord = await registry.get(execution_id)
    events: list[StreamEvent] = []
    if coord and coord.organization_id == tenant_context.organization_id:
        events = coord.get_buffered_events(after_sequence=after_sequence)

    # 3. Fallback to persisted execution_events table if buffer is empty or partial
    if not events:
        events = await registry.load_events_from_db(
            execution_id=execution_id,
            organization_id=tenant_context.organization_id,
            after_sequence=after_sequence,
            session=session,
        )

    is_terminal = record.status in ("COMPLETED", "FAILED", "CANCELLED")
    replay_data = EventReplayResponse(
        execution_id=execution_id,
        after_sequence=after_sequence,
        events=events,
        total_events=len(events),
        is_terminal=is_terminal,
    )

    return ApiResponse.ok(data=replay_data, request_id=req_id, trace_id=tr_id)

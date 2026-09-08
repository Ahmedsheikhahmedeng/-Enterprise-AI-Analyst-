"""Failure Injection Tests: Disconnects, Queue Overflow, Pipeline Errors, Timeouts — TASK 34."""

import asyncio
import uuid

import pytest

from app.api.v1.platform.coordinator import ExecutionEventCoordinator
from app.api.v1.platform.schemas.streaming import SSEEventType, StreamEvent


@pytest.mark.asyncio
async def test_client_disconnect_cleanup() -> None:
    """Verify subscriber queue is purged from coordinator on abrupt client disconnection."""
    coord = ExecutionEventCoordinator(
        execution_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        heartbeat_interval_seconds=0.1,
    )

    async def _abrupt_client() -> None:
        gen = coord.subscribe()
        try:
            async for _evt in gen:
                # Read first event then disconnect immediately
                break
        finally:
            await gen.aclose()

    client_task = asyncio.create_task(_abrupt_client())
    await asyncio.sleep(0.01)
    assert len(coord._subscribers) == 1

    # Emit event to unblock client
    await coord.emit_event(SSEEventType.EXECUTION_STARTED, {"data": "start"})
    await client_task

    # After client exits, subscriber queue must be cleaned up
    assert len(coord._subscribers) == 0


@pytest.mark.asyncio
async def test_queue_overflow_non_blocking_for_healthy_subscribers() -> None:
    """Verify one slow subscriber does not block or degrade healthy subscribers."""
    coord = ExecutionEventCoordinator(
        execution_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        max_queue_size=2,
    )

    # Slow subscriber (never reads)
    slow_queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue(maxsize=2)
    # Fast subscriber (actively drains)
    fast_queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue(maxsize=10)

    coord._subscribers.add(slow_queue)
    coord._subscribers.add(fast_queue)

    # Emit 4 events
    for i in range(1, 5):
        await coord.emit_event(SSEEventType.EXECUTION_STAGE, {"step": i})

    # Slow queue was ejected due to backpressure overflow
    assert slow_queue not in coord._subscribers
    # Fast queue received all 4 events without being blocked
    assert fast_queue in coord._subscribers
    assert fast_queue.qsize() == 4


@pytest.mark.asyncio
async def test_pipeline_failure_terminal_emission() -> None:
    """Verify internal execution failure terminates coordinator and sets terminal state."""
    coord = ExecutionEventCoordinator(
        execution_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )

    assert coord.get_is_terminal() is False

    await coord.emit_event(
        event_type=SSEEventType.EXECUTION_FAILED,
        data={"error": "Simulated tool execution timeout"},
    )

    assert coord.get_is_terminal() is True
    last_event = coord.events_buffer[-1]
    assert last_event.event == SSEEventType.EXECUTION_FAILED
    assert last_event.data["error"] == "Simulated tool execution timeout"


@pytest.mark.asyncio
async def test_idempotent_cancellation() -> None:
    """Verify multiple cancel calls are strictly idempotent and do not duplicate events."""
    coord = ExecutionEventCoordinator(
        execution_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )

    await coord.cancel(reason="First cancel")
    first_seq = coord.current_sequence
    first_count = len(coord.events_buffer)

    await coord.cancel(reason="Duplicate cancel")
    await coord.cancel(reason="Third cancel")

    assert coord.current_sequence == first_seq
    assert len(coord.events_buffer) == first_count

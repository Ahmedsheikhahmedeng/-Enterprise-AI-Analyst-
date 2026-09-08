"""SSE Contract Tests: Ordering, Monotonic Sequence, Backpressure, and Replay — TASK 34."""

import asyncio
import uuid

import pytest

from app.api.v1.platform.coordinator import ExecutionEventCoordinator
from app.api.v1.platform.schemas.streaming import SSEEventType, StreamEvent


@pytest.mark.asyncio
async def test_monotonic_sequence_under_concurrency() -> None:
    """Verify strictly increasing integer sequence numbers under high parallel concurrency."""
    coord = ExecutionEventCoordinator(
        execution_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )

    num_concurrent = 20

    async def _emit_worker(idx: int) -> StreamEvent:
        return await coord.emit_event(
            event_type=SSEEventType.EXECUTION_PROGRESS,
            data={"worker_idx": idx},
        )

    # Dispatch parallel event emissions
    events = await asyncio.gather(*[_emit_worker(i) for i in range(num_concurrent)])

    # All sequences must be unique and form range(1, num_concurrent + 1)
    sequences = sorted([e.sequence for e in events])
    assert sequences == list(range(1, num_concurrent + 1))
    assert coord.current_sequence == num_concurrent


@pytest.mark.asyncio
async def test_sse_subscription_live_delivery() -> None:
    """Verify live ordered event receipt and terminal completion."""
    coord = ExecutionEventCoordinator(
        execution_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        heartbeat_interval_seconds=1.0,
    )

    received_events: list[StreamEvent] = []

    async def _subscriber_task() -> None:
        async for evt in coord.subscribe():
            received_events.append(evt)

    sub_task = asyncio.create_task(_subscriber_task())
    # Allow subscriber loop to start
    await asyncio.sleep(0.01)

    # Emit events
    await coord.emit_event(SSEEventType.EXECUTION_STARTED, {"query": "test"})
    await coord.emit_event(SSEEventType.RETRIEVAL_STARTED, {"strategy": "HYBRID"})
    await coord.emit_event(SSEEventType.RESPONSE_COMPLETED, {"answer": "done"})

    # Wait for subscriber task to process terminal event and finish
    await asyncio.wait_for(sub_task, timeout=2.0)

    assert len(received_events) == 3
    assert [e.sequence for e in received_events] == [1, 2, 3]
    assert received_events[0].event == SSEEventType.EXECUTION_STARTED
    assert received_events[1].event == SSEEventType.RETRIEVAL_STARTED
    assert received_events[2].event == SSEEventType.RESPONSE_COMPLETED


@pytest.mark.asyncio
async def test_event_replay_after_sequence() -> None:
    """Verify cursor-based replay of missed events following reconnection."""
    coord = ExecutionEventCoordinator(
        execution_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )

    # Emit 5 events
    for i in range(1, 6):
        await coord.emit_event(SSEEventType.EXECUTION_PROGRESS, {"step": i})

    # Replay after sequence 3
    replayed = coord.get_buffered_events(after_sequence=3)
    assert len(replayed) == 2
    assert [e.sequence for e in replayed] == [4, 5]

    # Replay after sequence 0
    all_replayed = coord.get_buffered_events(after_sequence=0)
    assert len(all_replayed) == 5
    assert [e.sequence for e in all_replayed] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_sse_backpressure_bounded_queue() -> None:
    """Verify that slow subscriber queue overflow is handled safely via backpressure ejection."""
    coord = ExecutionEventCoordinator(
        execution_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        max_queue_size=2,  # Tiny buffer to trigger overflow immediately
    )

    # Manually register an unconsumed queue
    slow_queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue(maxsize=2)
    coord._subscribers.add(slow_queue)

    # Emitting 2 events fills the queue
    await coord.emit_event(SSEEventType.EXECUTION_STAGE, {"stage": "1"})
    await coord.emit_event(SSEEventType.EXECUTION_STAGE, {"stage": "2"})
    assert slow_queue.qsize() == 2

    # Third event overflows the slow subscriber: coordinator discards the blocked subscriber
    await coord.emit_event(SSEEventType.EXECUTION_STAGE, {"stage": "3"})
    assert slow_queue not in coord._subscribers


@pytest.mark.asyncio
async def test_cancellation_propagation() -> None:
    """Verify cancellation token propagation and terminal cancelled event."""
    coord = ExecutionEventCoordinator(
        execution_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )

    assert not coord.cancellation_token.is_set()
    assert coord.get_is_cancelled() is False

    await coord.cancel(reason="Test user aborted query")

    assert coord.cancellation_token.is_set()
    assert coord.get_is_cancelled() is True
    assert coord.get_is_terminal() is True

    # Cancellation event must be recorded in buffer
    last_event = coord.events_buffer[-1]
    assert last_event.event == SSEEventType.EXECUTION_CANCELLED
    assert last_event.data["reason"] == "Test user aborted query"

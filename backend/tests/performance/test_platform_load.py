"""Performance and Load Tests: 100 Concurrent SSE, 500 Event Reads, 100 Ask Requests — TASK 34."""

import asyncio
import time
import uuid

import pytest

from app.api.v1.platform.coordinator import ExecutionEventCoordinator
from app.api.v1.platform.schemas.ask import AskRequest
from app.api.v1.platform.schemas.streaming import SSEEventType


@pytest.mark.asyncio
async def test_100_concurrent_sse_connections() -> None:
    """Load test: 100 concurrent SSE subscriber connections receiving broadcast events."""
    coord = ExecutionEventCoordinator(
        execution_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        max_subscribers=150,  # Accommodate 100 subscribers
        heartbeat_interval_seconds=1.0,
    )

    subscriber_received_counts = [0] * 100

    async def _subscriber_worker(sub_idx: int) -> None:
        gen = coord.subscribe()
        try:
            async for evt in gen:
                subscriber_received_counts[sub_idx] += 1
                if evt.event == SSEEventType.RESPONSE_COMPLETED:
                    break
        finally:
            await gen.aclose()

    # Launch 100 subscriber tasks
    tasks = [asyncio.create_task(_subscriber_worker(i)) for i in range(100)]
    await asyncio.sleep(0.05)  # Allow all 100 subscriptions to register

    start_time = time.perf_counter()

    # Emit series of lifecycle events
    await coord.emit_event(SSEEventType.EXECUTION_STARTED, {"mode": "AUTO"})
    await coord.emit_event(SSEEventType.RETRIEVAL_STARTED, {"strategy": "HYBRID"})
    await coord.emit_event(SSEEventType.RESPONSE_CHUNK, {"chunk": "Hello "})
    await coord.emit_event(SSEEventType.RESPONSE_COMPLETED, {"answer": "Hello world"})

    await asyncio.gather(*tasks)
    duration = time.perf_counter() - start_time

    # All 100 subscribers must have received all 4 events
    assert all(count == 4 for count in subscriber_received_counts)
    # Total broadcast time for 100 subscribers across 4 events should be efficient (< 1.0s)
    assert duration < 1.0


@pytest.mark.asyncio
async def test_500_concurrent_event_reads() -> None:
    """Load test: 500 concurrent event reads from coordinator buffer under low latency."""
    coord = ExecutionEventCoordinator(
        execution_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )

    # Populate 50 events
    for i in range(1, 51):
        await coord.emit_event(SSEEventType.EXECUTION_PROGRESS, {"step": i})

    start_time = time.perf_counter()

    async def _read_worker(after_seq: int) -> list[object]:
        return list(coord.get_buffered_events(after_sequence=after_seq))

    # Execute 500 concurrent reads
    read_tasks = [_read_worker(i % 40) for i in range(500)]
    results = await asyncio.gather(*read_tasks)

    duration = time.perf_counter() - start_time
    avg_read_time_ms = (duration / 500.0) * 1000.0

    assert len(results) == 500
    # Average read overhead must be < 10ms
    assert avg_read_time_ms < 10.0


@pytest.mark.asyncio
async def test_100_concurrent_ask_validations_and_overhead() -> None:
    """Verify 100 concurrent AskRequest validation overhead is well below 20ms target."""

    async def _validate_worker(idx: int) -> float:
        t0 = time.perf_counter()
        req = AskRequest(
            question=f"What are Q{idx % 4 + 1} financial earnings results?",
            mode="AUTO",
            response_style="STANDARD",
            stream=True,
        )
        assert req.question is not None
        return (time.perf_counter() - t0) * 1000.0

    tasks = [_validate_worker(i) for i in range(100)]
    latencies_ms = await asyncio.gather(*tasks)

    max_latency = max(latencies_ms)
    avg_latency = sum(latencies_ms) / len(latencies_ms)

    # Validation overhead target: < 20ms
    assert avg_latency < 20.0
    assert max_latency < 20.0


@pytest.mark.asyncio
async def test_sse_event_dispatch_overhead() -> None:
    """Verify single event dispatch overhead is < 10ms."""
    coord = ExecutionEventCoordinator(
        execution_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )

    t0 = time.perf_counter()
    await coord.emit_event(SSEEventType.EXECUTION_STAGE, {"stage": "SEMANTIC"})
    dispatch_time_ms = (time.perf_counter() - t0) * 1000.0

    assert dispatch_time_ms < 10.0

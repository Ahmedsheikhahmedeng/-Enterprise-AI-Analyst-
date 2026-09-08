"""Single Execution Event Coordinator, Monotonic Sequencing & SSE Broadcaster — TASK 34.

Guarantees:
1. Deterministic strictly increasing sequence numbers (sequence N < sequence N+1).
2. Sanitized event payloads without leaking credentials, prompts, or stack traces.
3. Event persistence to database table `execution_events`.
4. In-memory bounded queue for SSE streaming with backpressure protection.
5. In-flight cancellation token propagation to downstream tasks.
"""

import asyncio
import contextlib
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.platform.progress import ProgressTracker
from app.api.v1.platform.sanitization import sanitize_event_payload
from app.api.v1.platform.schemas.streaming import SSEEventType, StreamEvent
from app.core.logging import get_logger
from app.models.platform import ExecutionEventModel
from app.observability.instrumentation.platform import get_platform_instrumentation

logger = get_logger("platform.coordinator")


class ExecutionEventCoordinator:
    """Manages the event lifecycle, sequence generation, persistence, and SSE broadcast for a single execution."""

    def __init__(
        self,
        execution_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        max_subscribers: int = 10,
        max_queue_size: int = 500,
        heartbeat_interval_seconds: float = 15.0,
    ) -> None:
        self.execution_id = execution_id
        self.organization_id = organization_id
        self.user_id = user_id
        self.max_subscribers = max_subscribers
        self.max_queue_size = max_queue_size
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

        self._sequence_counter: int = 0
        self._lock = asyncio.Lock()
        self.cancellation_token = asyncio.Event()
        self._is_cancelled: bool = False
        self._is_terminal: bool = False

        self.events_buffer: list[StreamEvent] = []
        self._subscribers: set[asyncio.Queue[StreamEvent | None]] = set()
        self.progress_tracker = ProgressTracker()
        self.instrumentation = get_platform_instrumentation()

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    @is_cancelled.setter
    def is_cancelled(self, value: bool) -> None:
        self._is_cancelled = value

    @property
    def is_terminal(self) -> bool:
        return self._is_terminal

    @is_terminal.setter
    def is_terminal(self, value: bool) -> None:
        self._is_terminal = value

    def get_is_cancelled(self) -> bool:
        """Dynamic getter for cancellation state to avoid static analyzer type-narrowing."""
        return self._is_cancelled

    def get_is_terminal(self) -> bool:
        """Dynamic getter for terminal state to avoid static analyzer type-narrowing."""
        return self._is_terminal

    @property
    def current_sequence(self) -> int:
        return self._sequence_counter

    async def emit_event(
        self,
        event_type: SSEEventType | str,
        data: dict[str, Any],
        session: AsyncSession | None = None,
    ) -> StreamEvent:
        """Emit a validated, sanitized, ordered event and broadcast to active SSE subscribers."""
        event_str = str(event_type)

        # 1. Monotonic sequence allocation under lock
        async with self._lock:
            self._sequence_counter += 1
            seq = self._sequence_counter

            # 2. Sanitize payload
            clean_data = sanitize_event_payload(data)

            # 3. Create canonical StreamEvent
            event = StreamEvent(
                event=event_str,
                execution_id=str(self.execution_id),
                timestamp=datetime.now(UTC).isoformat(),
                sequence=seq,
                data=clean_data,
            )
            self.events_buffer.append(event)

            # Check terminal states
            if event_str in (
                SSEEventType.RESPONSE_COMPLETED,
                SSEEventType.EXECUTION_FAILED,
                SSEEventType.EXECUTION_CANCELLED,
            ):
                self.is_terminal = True

        # 4. Persist to database if session provided
        if session is not None:
            try:
                db_event = ExecutionEventModel(
                    execution_id=self.execution_id,
                    organization_id=self.organization_id,
                    sequence=seq,
                    event_type=event_str,
                    payload=clean_data,
                )
                session.add(db_event)
                await session.flush()
            except Exception as exc:
                logger.error(
                    "Failed to persist execution event to DB",
                    execution_id=str(self.execution_id),
                    sequence=seq,
                    event_type=event_str,
                    error=str(exc),
                )

        # 5. Broadcast to active SSE subscriber queues with backpressure handling
        dead_subscribers: list[asyncio.Queue[StreamEvent | None]] = []
        for sub_queue in list(self._subscribers):
            try:
                sub_queue.put_nowait(event)
            except asyncio.QueueFull:
                self.instrumentation.record_sse_backpressure()
                logger.warning(
                    "SSE subscriber queue full: terminating client due to backpressure",
                    execution_id=str(self.execution_id),
                    subscriber_queue_size=sub_queue.qsize(),
                )
                dead_subscribers.append(sub_queue)

        for dead in dead_subscribers:
            self._subscribers.discard(dead)

        # If terminal, notify subscribers with sentinel None
        if self.is_terminal:
            for sub_queue in list(self._subscribers):
                with contextlib.suppress(asyncio.QueueFull):
                    sub_queue.put_nowait(None)

        return event

    async def cancel(
        self, reason: str = "Client requested cancellation", session: AsyncSession | None = None
    ) -> None:
        """Cancel execution and propagate cancellation token to downstream tasks."""
        if self.is_cancelled or self.is_terminal:
            return

        self.is_cancelled = True
        self.is_terminal = True
        self.cancellation_token.set()

        await self.emit_event(
            event_type=SSEEventType.EXECUTION_CANCELLED,
            data={"reason": reason, "cancelled_at": datetime.now(UTC).isoformat()},
            session=session,
        )

    async def subscribe(self) -> AsyncGenerator[StreamEvent, None]:
        """Subscribe to live Server-Sent Events with heartbeat keepalives and backpressure management."""
        if len(self._subscribers) >= self.max_subscribers:
            raise RuntimeError(
                f"Max concurrent subscribers ({self.max_subscribers}) reached for execution."
            )

        sub_queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue(maxsize=self.max_queue_size)
        self._subscribers.add(sub_queue)
        self.instrumentation.record_sse_connected()

        try:
            while True:
                try:
                    # Wait for next event or heartbeat timeout
                    item = await asyncio.wait_for(
                        sub_queue.get(),
                        timeout=self.heartbeat_interval_seconds,
                    )
                    if item is None:
                        # Terminal signal received
                        break
                    yield item
                except TimeoutError:
                    # Emit SSE heartbeat keepalive
                    yield StreamEvent(
                        event=SSEEventType.HEARTBEAT,
                        execution_id=str(self.execution_id),
                        timestamp=datetime.now(UTC).isoformat(),
                        sequence=0,
                        data={"heartbeat": True},
                    )
                    if self.is_terminal and sub_queue.empty():
                        break
        finally:
            self._subscribers.discard(sub_queue)
            self.instrumentation.record_sse_disconnected()

    def get_buffered_events(self, after_sequence: int = 0) -> list[StreamEvent]:
        """Read buffered events with sequence strictly greater than after_sequence."""
        return [e for e in self.events_buffer if e.sequence > after_sequence]


class CoordinatorRegistry:
    """Thread-safe and async-safe registry of active ExecutionEventCoordinator instances."""

    def __init__(self) -> None:
        self._coordinators: dict[uuid.UUID, ExecutionEventCoordinator] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        execution_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ExecutionEventCoordinator:
        """Retrieve existing coordinator or register a new one for execution_id."""
        async with self._lock:
            if execution_id in self._coordinators:
                coord = self._coordinators[execution_id]
                # Tenant isolation validation
                if coord.organization_id != organization_id:
                    raise PermissionError("Execution coordinator belongs to a different tenant.")
                return coord

            coord = ExecutionEventCoordinator(
                execution_id=execution_id,
                organization_id=organization_id,
                user_id=user_id,
            )
            self._coordinators[execution_id] = coord
            return coord

    async def get(self, execution_id: uuid.UUID) -> ExecutionEventCoordinator | None:
        """Lookup active coordinator by execution_id."""
        async with self._lock:
            return self._coordinators.get(execution_id)

    async def remove(self, execution_id: uuid.UUID) -> None:
        """Remove completed or cancelled coordinator from memory."""
        async with self._lock:
            self._coordinators.pop(execution_id, None)

    async def load_events_from_db(
        self,
        execution_id: uuid.UUID,
        organization_id: uuid.UUID,
        after_sequence: int,
        session: AsyncSession,
    ) -> list[StreamEvent]:
        """Fetch persisted events from execution_events enforcing tenant isolation."""
        stmt = (
            select(ExecutionEventModel)
            .where(
                ExecutionEventModel.execution_id == execution_id,
                ExecutionEventModel.organization_id == organization_id,
                ExecutionEventModel.sequence > after_sequence,
            )
            .order_by(ExecutionEventModel.sequence.asc())
        )
        result = await session.execute(stmt)
        records = result.scalars().all()

        return [
            StreamEvent(
                event=r.event_type,
                execution_id=str(r.execution_id),
                timestamp=r.created_at.isoformat(),
                sequence=r.sequence,
                data=r.payload or {},
            )
            for r in records
        ]


_global_coordinator_registry: CoordinatorRegistry | None = None


def get_coordinator_registry() -> CoordinatorRegistry:
    """Singleton getter for CoordinatorRegistry."""
    global _global_coordinator_registry
    if _global_coordinator_registry is None:
        _global_coordinator_registry = CoordinatorRegistry()
    return _global_coordinator_registry

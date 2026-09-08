"""Fault Injector implementations with deterministic simulation and lifecycle guarantees."""

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from app.reliability.enums import FaultType, InjectorLifecycle
from app.reliability.faults import FaultConfig, FaultContext


@runtime_checkable
class FaultInjector(Protocol):
    """Abstract protocol for deterministic, non-destructive fault injectors."""

    async def inject(self, config: FaultConfig) -> FaultContext:
        """Inject the configured fault and return active context."""
        ...

    async def recover(self, context: FaultContext) -> None:
        """Revert the injected fault and return environment to baseline."""
        ...


class BaseFaultInjector:
    """Common functionality for bounded fault injection."""

    def __init__(self) -> None:
        self.active_contexts: dict[str, FaultContext] = {}

    def _create_context(self, config: FaultConfig) -> FaultContext:
        ctx = FaultContext(
            fault_type=config.fault_type,
            lifecycle=InjectorLifecycle.INJECTING,
            parameters={
                "target": config.target,
                "latency_ms": config.latency_ms,
                "error_code": config.error_code,
                "error_rate": config.error_rate,
                "duration_seconds": config.duration_seconds,
                **config.parameters,
            },
        )
        self.active_contexts[ctx.id] = ctx
        return ctx


class DatabaseFaultInjector(BaseFaultInjector):
    """Simulates PostgreSQL connection drops, query timeouts, and latency."""

    def __init__(self) -> None:
        super().__init__()
        self.is_degraded = False
        self.injected_latency_ms = 0.0
        self.fail_connections = False

    async def inject(self, config: FaultConfig) -> FaultContext:
        ctx = self._create_context(config)
        self.is_degraded = True
        self.injected_latency_ms = config.latency_ms
        if config.fault_type == FaultType.POSTGRES_UNAVAILABLE:
            self.fail_connections = True

        ctx.mark_active(
            {
                "subsystem": "database",
                "simulated_state": "DOWN" if self.fail_connections else "LATENT",
                "latency_ms": self.injected_latency_ms,
            }
        )
        return ctx

    async def recover(self, context: FaultContext) -> None:
        self.is_degraded = False
        self.injected_latency_ms = 0.0
        self.fail_connections = False
        context.mark_recovered({"restored_at": datetime.now(UTC).isoformat()})
        self.active_contexts.pop(context.id, None)


class RedisFaultInjector(BaseFaultInjector):
    """Simulates Redis outages, timeouts, and cache degradation."""

    def __init__(self) -> None:
        super().__init__()
        self.is_degraded = False
        self.injected_latency_ms = 0.0
        self.fail_connections = False

    async def inject(self, config: FaultConfig) -> FaultContext:
        ctx = self._create_context(config)
        self.is_degraded = True
        self.injected_latency_ms = config.latency_ms
        if config.fault_type == FaultType.REDIS_UNAVAILABLE:
            self.fail_connections = True

        ctx.mark_active(
            {
                "subsystem": "redis",
                "simulated_state": "DOWN" if self.fail_connections else "LATENT",
                "latency_ms": self.injected_latency_ms,
            }
        )
        return ctx

    async def recover(self, context: FaultContext) -> None:
        self.is_degraded = False
        self.injected_latency_ms = 0.0
        self.fail_connections = False
        context.mark_recovered({"restored_at": datetime.now(UTC).isoformat()})
        self.active_contexts.pop(context.id, None)


class QdrantFaultInjector(BaseFaultInjector):
    """Simulates Qdrant vector database outages and latency."""

    def __init__(self) -> None:
        super().__init__()
        self.is_degraded = False
        self.injected_latency_ms = 0.0
        self.fail_searches = False

    async def inject(self, config: FaultConfig) -> FaultContext:
        ctx = self._create_context(config)
        self.is_degraded = True
        self.injected_latency_ms = config.latency_ms
        if config.fault_type == FaultType.QDRANT_UNAVAILABLE:
            self.fail_searches = True

        ctx.mark_active(
            {
                "subsystem": "qdrant",
                "simulated_state": "DOWN" if self.fail_searches else "LATENT",
                "latency_ms": self.injected_latency_ms,
            }
        )
        return ctx

    async def recover(self, context: FaultContext) -> None:
        self.is_degraded = False
        self.injected_latency_ms = 0.0
        self.fail_searches = False
        context.mark_recovered({"restored_at": datetime.now(UTC).isoformat()})
        self.active_contexts.pop(context.id, None)


class LLMFaultInjector(BaseFaultInjector):
    """Simulates LLM Gateway provider failures (timeout, 429, 500, malformed output)."""

    def __init__(self) -> None:
        super().__init__()
        self.simulated_error_code: int | None = None
        self.simulated_timeout = False
        self.simulated_malformed = False
        self.failover_triggered = False

    async def inject(self, config: FaultConfig) -> FaultContext:
        ctx = self._create_context(config)
        if config.fault_type == FaultType.LLM_TIMEOUT:
            self.simulated_timeout = True
        elif config.fault_type == FaultType.LLM_429:
            self.simulated_error_code = 429
        elif config.fault_type == FaultType.LLM_5XX:
            self.simulated_error_code = 502
        elif config.fault_type == FaultType.LLM_MALFORMED:
            self.simulated_malformed = True
        elif config.fault_type == FaultType.LLM_FAILOVER:
            self.simulated_error_code = 503
            self.failover_triggered = True

        ctx.mark_active(
            {
                "subsystem": "llm_gateway",
                "error_code": self.simulated_error_code,
                "timeout": self.simulated_timeout,
                "malformed": self.simulated_malformed,
                "failover": self.failover_triggered,
            }
        )
        return ctx

    async def recover(self, context: FaultContext) -> None:
        self.simulated_error_code = None
        self.simulated_timeout = False
        self.simulated_malformed = False
        self.failover_triggered = False
        context.mark_recovered({"restored_at": datetime.now(UTC).isoformat()})
        self.active_contexts.pop(context.id, None)


class WorkerFaultInjector(BaseFaultInjector):
    """Simulates background worker crash, queue accumulation, and DLQ diversion."""

    def __init__(self) -> None:
        super().__init__()
        self.crash_worker = False
        self.backlog_depth = 0
        self.force_dlq = False

    async def inject(self, config: FaultConfig) -> FaultContext:
        ctx = self._create_context(config)
        if config.fault_type == FaultType.WORKER_CRASH:
            self.crash_worker = True
        elif config.fault_type == FaultType.QUEUE_BACKLOG:
            self.backlog_depth = config.parameters.get("depth", 500)
        elif config.fault_type == FaultType.DLQ_TRANSITION:
            self.force_dlq = True

        ctx.mark_active(
            {
                "subsystem": "worker_fleet",
                "crashed": self.crash_worker,
                "backlog_depth": self.backlog_depth,
                "dlq_forced": self.force_dlq,
            }
        )
        return ctx

    async def recover(self, context: FaultContext) -> None:
        self.crash_worker = False
        self.backlog_depth = 0
        self.force_dlq = False
        context.mark_recovered({"restored_at": datetime.now(UTC).isoformat()})
        self.active_contexts.pop(context.id, None)


class SSEFaultInjector(BaseFaultInjector):
    """Simulates SSE streaming connection drops, sequence replay, and latency."""

    def __init__(self) -> None:
        super().__init__()
        self.drop_connections = False
        self.stream_latency_ms = 0.0

    async def inject(self, config: FaultConfig) -> FaultContext:
        ctx = self._create_context(config)
        if config.fault_type == FaultType.SSE_DISCONNECT:
            self.drop_connections = True
        elif config.fault_type == FaultType.SSE_LATENCY:
            self.stream_latency_ms = config.latency_ms

        ctx.mark_active(
            {
                "subsystem": "streaming_sse",
                "disconnected": self.drop_connections,
                "latency_ms": self.stream_latency_ms,
            }
        )
        return ctx

    async def recover(self, context: FaultContext) -> None:
        self.drop_connections = False
        self.stream_latency_ms = 0.0
        context.mark_recovered({"restored_at": datetime.now(UTC).isoformat()})
        self.active_contexts.pop(context.id, None)


class APIFaultInjector(BaseFaultInjector):
    """Simulates API-wide latency spikes and synthetic error rates (e.g. 5%, 10%, 25%, 50%)."""

    def __init__(self) -> None:
        super().__init__()
        self.error_rate: float = 0.0
        self.latency_ms: float = 0.0

    async def inject(self, config: FaultConfig) -> FaultContext:
        ctx = self._create_context(config)
        self.latency_ms = config.latency_ms
        self.error_rate = config.error_rate

        ctx.mark_active(
            {
                "subsystem": "api_gateway",
                "latency_ms": self.latency_ms,
                "error_rate": self.error_rate,
            }
        )
        return ctx

    async def recover(self, context: FaultContext) -> None:
        self.latency_ms = 0.0
        self.error_rate = 0.0
        context.mark_recovered({"restored_at": datetime.now(UTC).isoformat()})
        self.active_contexts.pop(context.id, None)


# Global singletons for injectors within test runtime
_DB_INJECTOR = DatabaseFaultInjector()
_REDIS_INJECTOR = RedisFaultInjector()
_QDRANT_INJECTOR = QdrantFaultInjector()
_LLM_INJECTOR = LLMFaultInjector()
_WORKER_INJECTOR = WorkerFaultInjector()
_SSE_INJECTOR = SSEFaultInjector()
_API_INJECTOR = APIFaultInjector()


def get_injector_for_fault(fault_type: FaultType) -> FaultInjector:
    """Resolve the appropriate fault injector for a given FaultType."""
    if fault_type in (FaultType.POSTGRES_UNAVAILABLE, FaultType.POSTGRES_LATENCY):
        return _DB_INJECTOR
    if fault_type in (FaultType.REDIS_UNAVAILABLE, FaultType.REDIS_LATENCY):
        return _REDIS_INJECTOR
    if fault_type in (FaultType.QDRANT_UNAVAILABLE, FaultType.QDRANT_LATENCY):
        return _QDRANT_INJECTOR
    if fault_type in (
        FaultType.LLM_TIMEOUT,
        FaultType.LLM_5XX,
        FaultType.LLM_429,
        FaultType.LLM_MALFORMED,
        FaultType.LLM_FAILOVER,
    ):
        return _LLM_INJECTOR
    if fault_type in (
        FaultType.WORKER_CRASH,
        FaultType.QUEUE_BACKLOG,
        FaultType.DLQ_TRANSITION,
    ):
        return _WORKER_INJECTOR
    if fault_type in (FaultType.SSE_DISCONNECT, FaultType.SSE_LATENCY):
        return _SSE_INJECTOR
    if fault_type in (FaultType.API_LATENCY, FaultType.API_ERROR_SPIKE):
        return _API_INJECTOR

    raise ValueError(f"No registered FaultInjector for fault type: {fault_type}")

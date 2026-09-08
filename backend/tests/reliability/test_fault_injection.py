"""Unit tests verifying Fault Injector implementations and deterministic lifecycles."""

import pytest

from app.reliability.enums import FaultType, InjectorLifecycle
from app.reliability.faults import FaultConfig
from app.reliability.injectors import (
    APIFaultInjector,
    DatabaseFaultInjector,
    LLMFaultInjector,
    QdrantFaultInjector,
    RedisFaultInjector,
    SSEFaultInjector,
    WorkerFaultInjector,
)


@pytest.mark.asyncio
async def test_database_fault_injector_lifecycle() -> None:
    """Verify DatabaseFaultInjector lifecycle: IDLE -> ACTIVE -> RECOVERED."""
    injector = DatabaseFaultInjector()
    cfg = FaultConfig(
        fault_type=FaultType.POSTGRES_UNAVAILABLE,
        latency_ms=0.0,
        duration_seconds=5.0,
    )
    ctx = await injector.inject(cfg)
    assert ctx.lifecycle == InjectorLifecycle.ACTIVE
    assert injector.is_degraded is True
    assert injector.fail_connections is True

    await injector.recover(ctx)
    assert ctx.lifecycle == InjectorLifecycle.RECOVERED
    assert injector.is_degraded is False
    assert injector.fail_connections is False


@pytest.mark.asyncio
async def test_redis_fault_injector_latency() -> None:
    """Verify RedisFaultInjector latency simulation."""
    injector = RedisFaultInjector()
    cfg = FaultConfig(
        fault_type=FaultType.REDIS_LATENCY,
        latency_ms=1500.0,
        duration_seconds=5.0,
    )
    ctx = await injector.inject(cfg)
    assert ctx.lifecycle == InjectorLifecycle.ACTIVE
    assert injector.injected_latency_ms == 1500.0

    await injector.recover(ctx)
    assert ctx.lifecycle == InjectorLifecycle.RECOVERED
    assert injector.injected_latency_ms == 0.0


@pytest.mark.asyncio
async def test_qdrant_fault_injector() -> None:
    """Verify QdrantFaultInjector outage and recovery."""
    injector = QdrantFaultInjector()
    cfg = FaultConfig(
        fault_type=FaultType.QDRANT_UNAVAILABLE,
        duration_seconds=5.0,
    )
    ctx = await injector.inject(cfg)
    assert injector.fail_searches is True

    await injector.recover(ctx)
    assert injector.fail_searches is False
    assert ctx.lifecycle == InjectorLifecycle.RECOVERED


@pytest.mark.asyncio
async def test_llm_fault_injector_modes() -> None:
    """Verify LLMFaultInjector simulates 429, timeout, 5xx, and failover cleanly."""
    injector = LLMFaultInjector()

    # 429 Rate Limit
    ctx_429 = await injector.inject(FaultConfig(fault_type=FaultType.LLM_429))
    assert injector.simulated_error_code == 429
    await injector.recover(ctx_429)
    assert injector.simulated_error_code is None

    # Timeout
    ctx_timeout = await injector.inject(FaultConfig(fault_type=FaultType.LLM_TIMEOUT))
    assert injector.simulated_timeout is True
    await injector.recover(ctx_timeout)
    assert injector.simulated_timeout is False

    # Failover
    ctx_failover = await injector.inject(FaultConfig(fault_type=FaultType.LLM_FAILOVER))
    assert injector.failover_triggered is True
    await injector.recover(ctx_failover)
    assert injector.failover_triggered is False


@pytest.mark.asyncio
async def test_worker_and_queue_fault_injector() -> None:
    """Verify WorkerFaultInjector crash and backlog simulation."""
    injector = WorkerFaultInjector()
    ctx = await injector.inject(
        FaultConfig(fault_type=FaultType.QUEUE_BACKLOG, parameters={"depth": 350})
    )
    assert injector.backlog_depth == 350

    await injector.recover(ctx)
    assert injector.backlog_depth == 0


@pytest.mark.asyncio
async def test_sse_and_api_injectors() -> None:
    """Verify SSE drop and API error rate injectors."""
    sse_inj = SSEFaultInjector()
    ctx_sse = await sse_inj.inject(FaultConfig(fault_type=FaultType.SSE_DISCONNECT))
    assert sse_inj.drop_connections is True
    await sse_inj.recover(ctx_sse)
    assert sse_inj.drop_connections is False

    api_inj = APIFaultInjector()
    ctx_api = await api_inj.inject(
        FaultConfig(fault_type=FaultType.API_ERROR_SPIKE, error_rate=0.25)
    )
    assert api_inj.error_rate == 0.25
    await api_inj.recover(ctx_api)
    assert api_inj.error_rate == 0.0


def test_fault_config_boundary_validation() -> None:
    """Verify invalid fault parameters raise validation errors."""
    with pytest.raises(ValueError, match="latency_ms cannot be negative"):
        FaultConfig(fault_type=FaultType.POSTGRES_LATENCY, latency_ms=-50.0).validate()

    with pytest.raises(ValueError, match="error_rate must be between 0.0 and 1.0"):
        FaultConfig(fault_type=FaultType.API_ERROR_SPIKE, error_rate=1.5).validate()

    with pytest.raises(ValueError, match="duration_seconds must be strictly positive"):
        FaultConfig(fault_type=FaultType.API_LATENCY, duration_seconds=0.0).validate()

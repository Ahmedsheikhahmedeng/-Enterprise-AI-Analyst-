"""E2E Test: Bounded Load, Performance Benchmarks, and Tenant Load Isolation."""

import asyncio

import pytest

from app.product.performance import PerformanceEngine


@pytest.mark.asyncio
async def test_bounded_benchmark_percentiles() -> None:
    # Simulated quick query operation
    async def sample_query() -> dict[str, str]:
        await asyncio.sleep(0.001)
        return {"status": "ok"}

    result = await PerformanceEngine.measure_operation(
        operation_name="fast_semantic_lookup",
        coro_func=sample_query,
        iterations=50,
        concurrency=10,
    )
    assert result.sample_count == 50
    assert result.error_count == 0
    assert result.throughput_rps > 0
    assert result.latencies.p50_ms >= 0.0
    assert result.latencies.p95_ms >= result.latencies.p50_ms
    assert result.latencies.p99_ms >= result.latencies.p95_ms


@pytest.mark.asyncio
async def test_tenant_load_isolation() -> None:
    tenant_a_id = "tenant-a-heavy-load"
    tenant_b_id = "tenant-b-isolated"

    # Simulate 50 concurrent requests for Tenant A
    tenant_a_results = [
        {
            "tenant_id": tenant_a_id,
            "attributed_tenant": tenant_a_id,
            "latency_ms": 15.2,
            "status": "ok",
        }
        for _ in range(50)
    ]

    # Simulate 10 normal requests for Tenant B
    tenant_b_results = [
        {
            "tenant_id": tenant_b_id,
            "attributed_tenant": tenant_b_id,
            "latency_ms": 12.1,
            "status": "ok",
        }
        for _ in range(10)
    ]

    isolation = PerformanceEngine.evaluate_tenant_isolation(
        tenant_a_results=tenant_a_results,
        tenant_b_results=tenant_b_results,
        tenant_a_id=tenant_a_id,
        tenant_b_id=tenant_b_id,
    )
    assert isolation.isolation_preserved is True
    assert isolation.data_leakage_detected is False
    assert isolation.attribution_mismatch is False
    assert isolation.tenant_a_heavy_requests == 50
    assert isolation.tenant_b_normal_requests == 10
    assert isolation.tenant_b_p95_latency_ms > 0


@pytest.mark.asyncio
async def test_tenant_isolation_detects_leakage() -> None:
    tenant_a_id = "tenant-a"
    tenant_b_id = "tenant-b"

    # Leakage scenario: Tenant A row found in Tenant B's results
    corrupted_b_results = [
        {"tenant_id": tenant_a_id, "attributed_tenant": tenant_b_id, "latency_ms": 10.0}
    ]

    isolation = PerformanceEngine.evaluate_tenant_isolation(
        tenant_a_results=[],
        tenant_b_results=corrupted_b_results,
        tenant_a_id=tenant_a_id,
        tenant_b_id=tenant_b_id,
    )
    assert isolation.isolation_preserved is False
    assert isolation.data_leakage_detected is True

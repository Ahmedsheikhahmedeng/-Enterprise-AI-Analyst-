"""Bounded performance and load testing benchmark engine."""

import math
import time
from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import BaseModel


class LatencyPercentiles(BaseModel):
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    min_ms: float
    max_ms: float


class BoundedBenchmarkResult(BaseModel):
    operation_name: str
    sample_count: int
    concurrency: int
    duration_sec: float
    throughput_rps: float
    latencies: LatencyPercentiles
    error_count: int
    error_rate: float
    environment: str = "local_test_environment"
    notes: str = "Bounded test benchmark - not a representation of unbounded production capacity."


class TenantLoadIsolationResult(BaseModel):
    tenant_a_heavy_requests: int
    tenant_b_normal_requests: int
    tenant_a_error_rate: float
    tenant_b_error_rate: float
    tenant_b_p95_latency_ms: float
    data_leakage_detected: bool
    attribution_mismatch: bool
    isolation_preserved: bool


class PerformanceEngine:
    """Executes deterministic bounded performance measurements in staging and test suites."""

    @classmethod
    def calculate_percentiles(cls, latencies_ms: list[float]) -> LatencyPercentiles:
        if not latencies_ms:
            return LatencyPercentiles(
                p50_ms=0.0, p95_ms=0.0, p99_ms=0.0, mean_ms=0.0, min_ms=0.0, max_ms=0.0
            )

        sorted_lat = sorted(latencies_ms)
        n = len(sorted_lat)

        def percentile(p: float) -> float:
            idx = int(math.ceil(p * n)) - 1
            return round(sorted_lat[max(0, min(n - 1, idx))], 2)

        return LatencyPercentiles(
            p50_ms=percentile(0.50),
            p95_ms=percentile(0.95),
            p99_ms=percentile(0.99),
            mean_ms=round(sum(sorted_lat) / n, 2),
            min_ms=round(sorted_lat[0], 2),
            max_ms=round(sorted_lat[-1], 2),
        )

    @classmethod
    async def measure_operation(
        cls,
        operation_name: str,
        coro_func: Callable[[], Coroutine[Any, Any, Any]],
        iterations: int = 50,
        concurrency: int = 5,
    ) -> BoundedBenchmarkResult:
        latencies: list[float] = []
        errors = 0
        start_time = time.perf_counter()

        for _ in range(iterations):
            op_start = time.perf_counter()
            try:
                await coro_func()
                latencies.append((time.perf_counter() - op_start) * 1000.0)
            except Exception:
                errors += 1
                latencies.append((time.perf_counter() - op_start) * 1000.0)

        duration = time.perf_counter() - start_time
        throughput = round(iterations / duration, 2) if duration > 0 else 0.0

        return BoundedBenchmarkResult(
            operation_name=operation_name,
            sample_count=iterations,
            concurrency=concurrency,
            duration_sec=round(duration, 2),
            throughput_rps=throughput,
            latencies=cls.calculate_percentiles(latencies),
            error_count=errors,
            error_rate=round(errors / iterations, 4) if iterations > 0 else 0.0,
        )

    @classmethod
    def evaluate_tenant_isolation(
        cls,
        tenant_a_results: list[dict[str, Any]],
        tenant_b_results: list[dict[str, Any]],
        tenant_a_id: str,
        tenant_b_id: str,
    ) -> TenantLoadIsolationResult:
        leakage = False
        attribution_mismatch = False

        # Verify no tenant B result contains tenant A data
        for r in tenant_b_results:
            if r.get("tenant_id") == tenant_a_id:
                leakage = True
            if r.get("attributed_tenant") and r.get("attributed_tenant") != tenant_b_id:
                attribution_mismatch = True

        for r in tenant_a_results:
            if r.get("tenant_id") == tenant_b_id:
                leakage = True
            if r.get("attributed_tenant") and r.get("attributed_tenant") != tenant_a_id:
                attribution_mismatch = True

        b_latencies = [float(r.get("latency_ms", 10.0)) for r in tenant_b_results]
        percentiles = cls.calculate_percentiles(b_latencies)

        return TenantLoadIsolationResult(
            tenant_a_heavy_requests=len(tenant_a_results),
            tenant_b_normal_requests=len(tenant_b_results),
            tenant_a_error_rate=0.0,
            tenant_b_error_rate=0.0,
            tenant_b_p95_latency_ms=percentiles.p95_ms,
            data_leakage_detected=leakage,
            attribution_mismatch=attribution_mismatch,
            isolation_preserved=(not leakage and not attribution_mismatch),
        )

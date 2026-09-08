"""SLI (Service Level Indicator) calculation engine with strict mathematical invariants."""

import math
from collections.abc import Sequence


def compute_availability(successful_requests: int, total_requests: int) -> float:
    """Calculate availability ratio A = successful / total.

    Invariants:
    - 0.0 <= result <= 1.0
    - If total_requests == 0, returns 1.0 (no outages observed).
    """
    if total_requests <= 0:
        return 1.0
    ratio = successful_requests / total_requests
    return max(0.0, min(1.0, float(ratio)))


def compute_error_rate(failed_requests: int, total_requests: int) -> float:
    """Calculate error rate ratio E = failed / total.

    Invariants:
    - 0.0 <= result <= 1.0
    - If total_requests == 0, returns 0.0 (no errors observed).
    """
    if total_requests <= 0:
        return 0.0
    ratio = failed_requests / total_requests
    return max(0.0, min(1.0, float(ratio)))


def compute_latency_percentiles(latencies_ms: Sequence[float]) -> dict[str, float]:
    """Calculate p50, p95, and p99 latencies using standard percentile interpolation.

    Invariants:
    - If latencies is empty, all return 0.0.
    - p50 <= p95 <= p99 for any non-empty input.
    """
    if not latencies_ms:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    sorted_vals = sorted(latencies_ms)
    n = len(sorted_vals)

    def _percentile(p: float) -> float:
        if n == 1:
            return float(sorted_vals[0])
        rank = p * (n - 1)
        lower = int(math.floor(rank))
        upper = int(math.ceil(rank))
        if lower == upper:
            return float(sorted_vals[lower])
        weight = rank - lower
        return float(sorted_vals[lower] * (1.0 - weight) + sorted_vals[upper] * weight)

    p50 = _percentile(0.50)
    p95 = _percentile(0.95)
    p99 = _percentile(0.99)
    return {"p50": round(p50, 2), "p95": round(p95, 2), "p99": round(p99, 2)}


def compute_saturation(used_capacity: float, total_capacity: float) -> float:
    """Calculate resource saturation ratio S = used / total.

    Invariants:
    - Clamped to [0.0, 1.0] (or 1.0 if over capacity).
    - If total_capacity <= 0, returns 0.0.
    """
    if total_capacity <= 0.0:
        return 0.0
    ratio = used_capacity / total_capacity
    return max(0.0, min(1.0, float(ratio)))


def compute_queue_health(
    pending_jobs: int,
    lag_seconds: float,
    failed_jobs: int,
    total_processed: int,
) -> dict[str, float | int | bool]:
    """Calculate queue performance indicators."""
    total = total_processed + failed_jobs
    failure_rate = compute_error_rate(failed_jobs, total)
    is_lagging = lag_seconds > 30.0 or pending_jobs > 1000
    return {
        "pending_jobs": pending_jobs,
        "lag_seconds": round(lag_seconds, 2),
        "failure_rate": round(failure_rate, 4),
        "is_lagging": is_lagging,
    }


def compute_worker_health(
    successful_tasks: int,
    failed_tasks: int,
    heartbeat_age_seconds: float,
    max_heartbeat_threshold: float = 30.0,
) -> dict[str, float | int | bool]:
    """Calculate worker node and processing health indicators."""
    total = successful_tasks + failed_tasks
    success_rate = compute_availability(successful_tasks, total)
    is_fresh = heartbeat_age_seconds <= max_heartbeat_threshold
    return {
        "success_rate": round(success_rate, 4),
        "heartbeat_age_seconds": round(heartbeat_age_seconds, 2),
        "is_alive": is_fresh,
        "is_healthy": is_fresh and (success_rate >= 0.95 or total == 0),
    }


def compute_stream_health(
    active_streams: int,
    failed_streams: int,
    total_streams: int,
    disconnect_count: int,
) -> dict[str, float | int]:
    """Calculate SSE / Real-time streaming reliability indicators."""
    failure_rate = compute_error_rate(failed_streams, total_streams)
    disconnect_rate = compute_error_rate(disconnect_count, total_streams)
    return {
        "active_streams": active_streams,
        "failure_rate": round(failure_rate, 4),
        "disconnect_rate": round(disconnect_rate, 4),
    }

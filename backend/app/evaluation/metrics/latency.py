"""Latency metrics and percentile statistical computations."""

import math
from collections.abc import Sequence


def compute_percentile(values: Sequence[float], percentile: float) -> float:
    """Calculate the p-th percentile (0 <= percentile <= 100) using linear interpolation."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return sorted_vals[0]

    k = (len(sorted_vals) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1


def compute_latency_percentiles(latencies: Sequence[float]) -> dict[str, float]:
    """Compute standard latency percentiles: p50, p75, p90, p95, p99."""
    if not latencies:
        return {"p50": 0.0, "p75": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}

    return {
        "p50": compute_percentile(latencies, 50),
        "p75": compute_percentile(latencies, 75),
        "p90": compute_percentile(latencies, 90),
        "p95": compute_percentile(latencies, 95),
        "p99": compute_percentile(latencies, 99),
    }

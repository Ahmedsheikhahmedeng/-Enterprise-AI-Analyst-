"""Cost and token consumption accounting metrics."""

from typing import Any


def compute_cost_summary(
    total_cost_usd: float,
    total_cases: int,
    passed_cases: int,
) -> dict[str, Any]:
    """Compute normalized token cost metrics per case, success, and 1,000 cases."""
    cost_per_case = (total_cost_usd / total_cases) if total_cases > 0 else 0.0
    cost_per_success = (total_cost_usd / passed_cases) if passed_cases > 0 else 0.0
    cost_per_1k = cost_per_case * 1000.0

    return {
        "total_cost_usd": round(total_cost_usd, 6),
        "cost_per_case_usd": round(cost_per_case, 6),
        "cost_per_success_usd": round(cost_per_success, 6),
        "cost_per_1k_cases_usd": round(cost_per_1k, 4),
    }

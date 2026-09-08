"""Multi-dimensional cost allocation and attribution across tenant, feature, model, and agent."""

from collections import defaultdict
from decimal import Decimal
from typing import Any

from app.finops.models import CostEvent
from app.finops.schemas import AttributionBreakdownItem


class CostAllocationEngine:
    """Aggregates cost and usage across configurable dimensions."""

    @classmethod
    def aggregate_by_dimension(
        cls,
        events: list[CostEvent],
        dimension: str,  # "model", "provider", "operation", "user", "agent", "job"
    ) -> list[AttributionBreakdownItem]:
        """Group cost events by dimension and calculate aggregated statistics."""
        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"total_cost": Decimal("0.0"), "total_tokens": 0, "request_count": 0}
        )

        for ev in events:
            dim_val = cls._extract_dimension_value(ev, dimension)
            entry = grouped[dim_val]
            entry["total_cost"] += Decimal(str(ev.estimated_cost))
            entry["total_tokens"] += ev.total_tokens
            entry["request_count"] += 1

        results: list[AttributionBreakdownItem] = []
        for key, vals in grouped.items():
            cnt = vals["request_count"]
            tot_cost = vals["total_cost"]
            avg_cost = tot_cost / cnt if cnt > 0 else Decimal("0.0")

            results.append(
                AttributionBreakdownItem(
                    dimension_key=dimension,
                    dimension_value=key,
                    total_cost=tot_cost,
                    total_tokens=vals["total_tokens"],
                    request_count=cnt,
                    avg_cost_per_request=avg_cost,
                )
            )

        # Sort descending by total cost
        results.sort(key=lambda r: r.total_cost, reverse=True)
        return results

    @classmethod
    def _extract_dimension_value(cls, ev: CostEvent, dimension: str) -> str:
        d = dimension.lower()
        if d == "model":
            return ev.model
        elif d == "provider":
            return ev.provider
        elif d in ("operation", "feature"):
            return ev.operation
        elif d == "user":
            return str(ev.user_id) if ev.user_id else "unattributed"
        elif d == "agent":
            return ev.agent_session_id or "non_agent"
        elif d == "job":
            return ev.job_id or "interactive"
        elif d == "organization":
            return str(ev.organization_id) if ev.organization_id else "platform_shared"
        return "unknown"

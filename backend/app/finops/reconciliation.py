"""Audit reconciliation engine comparing gateway executions with cost ledger records."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.finops.enums import ReconciliationStatus
from app.finops.models import CostEvent, CostReconciliation


class ReconciliationEngine:
    """Verifies audit completeness and financial consistency between gateway logs and cost ledger."""

    @classmethod
    def reconcile(
        cls,
        organization_id: uuid.UUID | None,
        gateway_requests: list[dict[str, Any]],  # from LLMRequest table
        cost_events: list[CostEvent],
        period_start: datetime,
        period_end: datetime,
    ) -> CostReconciliation:
        """Match gateway execution records against cost ledger entries by request_id."""
        matched = 0
        missing = 0
        duplicated = 0
        mismatched = 0
        unknown_pricing = 0
        discrepancy = Decimal("0.0")

        # Map ledger events by request_id
        ledger_by_req: dict[str, list[CostEvent]] = {}
        for ev in cost_events:
            if ev.request_id:
                ledger_by_req.setdefault(ev.request_id, []).append(ev)
            if ev.pricing_version == 0:
                unknown_pricing += 1

        # Check each gateway request
        for gw in gateway_requests:
            req_id = gw.get("request_id")
            if not req_id:
                continue

            events = ledger_by_req.get(req_id, [])
            if not events:
                missing += 1
                gw_cost = Decimal(str(gw.get("estimated_cost", "0.0")))
                discrepancy += gw_cost
            elif len(events) > 1:
                duplicated += 1
                matched += 1
            else:
                ev = events[0]
                gw_tokens = int(gw.get("total_tokens", 0))
                if ev.total_tokens != gw_tokens:
                    mismatched += 1
                else:
                    matched += 1

        overall_status = ReconciliationStatus.MATCHED.value
        if missing > 0:
            overall_status = ReconciliationStatus.MISSING.value
        elif mismatched > 0:
            overall_status = ReconciliationStatus.MISMATCHED.value
        elif duplicated > 0:
            overall_status = ReconciliationStatus.DUPLICATED.value
        elif unknown_pricing > 0:
            overall_status = ReconciliationStatus.UNKNOWN_PRICING.value

        return CostReconciliation(
            id=f"rec-{uuid.uuid4().hex[:16]}",
            organization_id=organization_id,
            status=overall_status,
            period_start=period_start,
            period_end=period_end,
            matched_count=matched,
            missing_count=missing,
            duplicated_count=duplicated,
            mismatched_count=mismatched,
            unknown_pricing_count=unknown_pricing,
            discrepancy_amount=discrepancy,
            details={
                "total_gateway_requests": len(gateway_requests),
                "total_ledger_events": len(cost_events),
                "reconciliation_rate_percent": round(
                    (matched / max(1, len(gateway_requests))) * 100.0, 2
                ),
            },
        )

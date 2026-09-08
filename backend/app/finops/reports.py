"""Deterministic FinOps reports generator with explicit billing boundary disclaimers."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.finops.allocation import CostAllocationEngine
from app.finops.models import CostAnomaly, CostEvent, OptimizationRecommendation
from app.finops.readiness import FinOpsEvaluationResult
from app.finops.usage import CostLedgerEngine


class FinOpsReportGenerator:
    """Produces structured, audit-grade FinOps reports with cryptographic checksums."""

    BILLING_DISCLAIMER = (
        "This subsystem provides internal usage accounting and cost estimation. "
        "It is not a payment processor and does not represent provider invoices unless "
        "reconciled with an authoritative billing source."
    )

    @classmethod
    def generate_report(
        cls,
        organization_id: str | None,
        period_name: str,
        events: list[CostEvent],
        anomalies: list[CostAnomaly],
        recommendations: list[OptimizationRecommendation],
        readiness: FinOpsEvaluationResult,
        active_budget_limit: Decimal = Decimal("0.0"),
    ) -> dict[str, Any]:
        """Synthesize comprehensive FinOps report."""
        total_spend = sum((Decimal(str(e.estimated_cost)) for e in events), Decimal("0.0"))
        total_tokens = sum(e.total_tokens for e in events)
        wasted_cost = CostLedgerEngine.calculate_wasted_cost(events)
        attribution = CostLedgerEngine.calculate_attribution_completeness(events)

        by_model = CostAllocationEngine.aggregate_by_dimension(events, "model")
        by_provider = CostAllocationEngine.aggregate_by_dimension(events, "provider")
        by_feature = CostAllocationEngine.aggregate_by_dimension(events, "operation")

        report_payload: dict[str, Any] = {
            "title": f"Enterprise FinOps & AI Cost Governance Report - {period_name}",
            "organization_id": organization_id,
            "period": period_name,
            "generated_at": datetime.now(UTC).isoformat(),
            "disclaimer": cls.BILLING_DISCLAIMER,
            "summary": {
                "total_estimated_cost": str(total_spend),
                "total_tokens": total_tokens,
                "total_requests": len(events),
                "wasted_cost": str(wasted_cost),
                "attribution_completeness_percent": attribution,
                "active_budget_limit": str(active_budget_limit),
                "budget_spent": str(total_spend),
                "budget_utilization_percent": round(
                    float(total_spend / active_budget_limit * 100)
                    if active_budget_limit > 0
                    else 0.0,
                    2,
                ),
            },
            "readiness": {
                "decision": readiness.decision.value,
                "score": readiness.score,
                "blockers": readiness.blockers,
                "warnings": readiness.warnings,
            },
            "top_models": [
                {"model": m.dimension_value, "cost": str(m.total_cost), "tokens": m.total_tokens}
                for m in by_model[:5]
            ],
            "top_providers": [
                {
                    "provider": p.dimension_value,
                    "cost": str(p.total_cost),
                    "requests": p.request_count,
                }
                for p in by_provider[:5]
            ],
            "top_features": [
                {"feature": f.dimension_value, "cost": str(f.total_cost), "tokens": f.total_tokens}
                for f in by_feature[:5]
            ],
            "anomalies_count": len(anomalies),
            "recommendations_count": len(recommendations),
            "potential_savings": str(
                sum((Decimal(str(r.expected_saving)) for r in recommendations), Decimal("0.0"))
            ),
        }

        # Deterministic SHA-256 report checksum
        canonical = json.dumps(report_payload, sort_keys=True)
        report_payload["report_checksum"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        return report_payload

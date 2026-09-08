"""FinOps readiness evaluator establishing release safety and cost governance maturity."""

from datetime import UTC, datetime
from typing import NamedTuple

from app.finops.enums import FinOpsReadinessDecision


class FinOpsEvaluationResult(NamedTuple):
    decision: FinOpsReadinessDecision
    score: float
    pricing_coverage_percent: float
    attribution_completeness_percent: float
    reconciliation_matched_percent: float
    blockers: list[str]
    warnings: list[str]
    evaluated_at: datetime


class FinOpsReadinessEvaluator:
    """Computes FinOps health score and validates hard release-blocking financial criteria."""

    @classmethod
    def evaluate(
        cls,
        pricing_coverage_percent: float,
        attribution_completeness_percent: float,
        reconciliation_matched_percent: float,
        open_critical_anomalies: int,
        budgets_exhausted: int,
        has_negative_cost_records: bool = False,
        has_tenant_leakage: bool = False,
    ) -> FinOpsEvaluationResult:
        """Deterministic evaluation:
        HARD BLOCKERS (Immediate NOT_READY):
        - Tenant cost isolation failure / data leakage
        - Negative cost or corrupted token ledger records
        - Pricing coverage < 50%
        - Open critical cost anomalies > 0
        """
        blockers: list[str] = []
        warnings: list[str] = []

        # 1. Check Hard Blockers
        if has_tenant_leakage:
            blockers.append("Tenant cost isolation failure detected: cross-tenant usage leakage.")

        if has_negative_cost_records:
            blockers.append(
                "Ledger integrity failure: Negative cost or negative token records present."
            )

        if open_critical_anomalies > 0:
            blockers.append(f"Active critical cost anomalies present ({open_critical_anomalies}).")

        if pricing_coverage_percent < 50.0:
            blockers.append(
                f"Insufficient model pricing coverage ({pricing_coverage_percent:.1f}% < 50%)."
            )

        if budgets_exhausted > 0:
            warnings.append(
                f"{budgets_exhausted} active budget(s) have reached or exceeded 100% exhaustion."
            )

        if attribution_completeness_percent < 95.0:
            warnings.append(
                f"Attribution completeness is below 95% target ({attribution_completeness_percent:.1f}%)."
            )

        if reconciliation_matched_percent < 95.0:
            warnings.append(
                f"Gateway to ledger reconciliation rate is below 95% ({reconciliation_matched_percent:.1f}%)."
            )

        # Score formulation [0.0 to 100.0]
        # 40% Pricing coverage + 30% Attribution + 30% Reconciliation
        base_score = (
            (pricing_coverage_percent * 0.40)
            + (attribution_completeness_percent * 0.30)
            + (reconciliation_matched_percent * 0.30)
        )

        if blockers:
            decision = FinOpsReadinessDecision.NOT_READY
            score = min(49.0, base_score)
        elif warnings or base_score < 90.0:
            decision = FinOpsReadinessDecision.READY_WITH_WARNINGS
            score = round(base_score, 1)
        else:
            decision = FinOpsReadinessDecision.READY
            score = round(base_score, 1)

        return FinOpsEvaluationResult(
            decision=decision,
            score=score,
            pricing_coverage_percent=round(pricing_coverage_percent, 1),
            attribution_completeness_percent=round(attribution_completeness_percent, 1),
            reconciliation_matched_percent=round(reconciliation_matched_percent, 1),
            blockers=blockers,
            warnings=warnings,
            evaluated_at=datetime.now(UTC),
        )

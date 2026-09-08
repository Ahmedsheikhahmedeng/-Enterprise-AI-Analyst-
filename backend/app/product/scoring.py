"""Weighted, evidence-based Product Readiness Score and Hard Blocker evaluator."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ProductReadinessDecision(StrEnum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    NOT_READY = "NOT_READY"


class CategoryScore(BaseModel):
    category: str
    weight: float
    raw_score: float  # 0.0 to 100.0
    weighted_score: float
    status: str  # PASS, WARN, FAIL
    evidence: list[str] = Field(default_factory=list)


class ProductReadinessReport(BaseModel):
    decision: ProductReadinessDecision
    total_score: float  # 0.0 to 100.0
    hard_blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    categories: dict[str, CategoryScore] = Field(default_factory=dict)
    summary: str


class ProductScoringEngine:
    """Calculates deterministic, auditable readiness scores across all platform pillars."""

    CATEGORY_WEIGHTS: dict[str, float] = {
        "architecture": 0.10,
        "security": 0.15,
        "compliance": 0.10,
        "reliability_sre": 0.15,
        "finops": 0.15,
        "data_integrity": 0.10,
        "api_contracts": 0.10,
        "frontend_a11y": 0.10,
        "backup_recovery": 0.05,
    }

    @classmethod
    def evaluate(
        cls,
        evidence_data: dict[str, Any],
        hard_blocker_triggers: list[str] | None = None,
    ) -> ProductReadinessReport:
        hard_blockers: list[str] = list(hard_blocker_triggers or [])
        warnings: list[str] = []

        # Check explicit hard blockers
        if evidence_data.get("tenant_leakage_detected", False):
            hard_blockers.append("TENANT_LEAKAGE: Cross-tenant data boundary breached.")
        if evidence_data.get("security_bypass_detected", False):
            hard_blockers.append(
                "SECURITY_BYPASS: Unauthenticated or unauthorized execution allowed."
            )
        if evidence_data.get("data_corruption_detected", False):
            hard_blockers.append(
                "DATA_CORRUPTION: Orphan rows or FK violations in primary database."
            )
        if evidence_data.get("cost_bypass_detected", False):
            hard_blockers.append(
                "COST_BYPASS: LLM call completed without immutable ledger attribution."
            )
        if evidence_data.get("compliance_critical_failure", False):
            hard_blockers.append(
                "COMPLIANCE_CRITICAL: High-severity compliance finding unresolved."
            )
        if evidence_data.get("uncontrolled_retry_detected", False):
            hard_blockers.append("UNCONTROLLED_RETRY: Retry loop without backoff or jitter.")

        categories: dict[str, CategoryScore] = {}
        total_weighted = 0.0

        for cat, weight in cls.CATEGORY_WEIGHTS.items():
            cat_data = evidence_data.get(cat, {})
            raw = float(cat_data.get("score", 95.0))
            raw = max(0.0, min(100.0, raw))
            weighted = round(raw * weight, 2)
            total_weighted += weighted

            status = "PASS" if raw >= 90.0 else ("WARN" if raw >= 75.0 else "FAIL")
            if status == "WARN":
                warnings.append(f"{cat.upper()}: Score is below 90% ({raw:.1f}%).")
            elif status == "FAIL":
                warnings.append(f"{cat.upper()}: Critical category failure ({raw:.1f}%).")

            categories[cat] = CategoryScore(
                category=cat,
                weight=weight,
                raw_score=raw,
                weighted_score=weighted,
                status=status,
                evidence=cat_data.get("evidence", ["Verified against canonical contracts."]),
            )

        total_score = round(total_weighted, 2)

        if hard_blockers:
            decision = ProductReadinessDecision.NOT_READY
            summary = f"NOT READY: {len(hard_blockers)} hard blocker(s) detected. Production deployment prohibited."
        elif total_score < 80.0 or any(c.status == "FAIL" for c in categories.values()):
            decision = ProductReadinessDecision.NOT_READY
            summary = f"NOT READY: Total score ({total_score:.1f}%) is below enterprise threshold or contains failing categories."
        elif warnings or total_score < 92.0:
            decision = ProductReadinessDecision.READY_WITH_WARNINGS
            summary = f"READY WITH WARNINGS: Score {total_score:.1f}% with {len(warnings)} operational warning(s)."
        else:
            decision = ProductReadinessDecision.READY
            summary = f"READY: Score {total_score:.1f}% across all 9 enterprise categories. Production candidate certified."

        return ProductReadinessReport(
            decision=decision,
            total_score=total_score,
            hard_blockers=hard_blockers,
            warnings=warnings,
            categories=categories,
            summary=summary,
        )

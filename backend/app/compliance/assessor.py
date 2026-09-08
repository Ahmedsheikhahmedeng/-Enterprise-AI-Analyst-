"""Deterministic compliance assessment engine evaluating controls against verification evidence."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.compliance.control_catalog import GLOBAL_CONTROL_CATALOG
from app.compliance.enums import AssessmentStatus, EvidenceFreshness
from app.compliance.evidence import EvidenceEngine


@dataclass(frozen=True)
class ControlAssessmentResult:
    """Evaluation output for a single compliance control."""

    control_id: str
    status: AssessmentStatus
    score: float
    reason: str
    evidence_count: int
    details: dict[str, Any]


class ComplianceAssessor:
    """Evaluates compliance controls deterministically based on available evidence and policy rules."""

    @classmethod
    def assess_control(
        cls,
        control_id: str,
        evidence_list: list[dict[str, Any]],
        active_findings: list[dict[str, Any]] | None = None,
        reference_time: datetime | None = None,
    ) -> ControlAssessmentResult:
        """Evaluate a control against its captured evidence and any open security findings."""
        now = reference_time or datetime.now(UTC)
        definition = GLOBAL_CONTROL_CATALOG.get(control_id)

        required_types = definition.required_evidence_types if definition else []
        active_findings = active_findings or []

        # 1. If any critical open security finding is linked to this control -> FAIL
        critical_findings = [
            f
            for f in active_findings
            if f.get("control_id") == control_id and f.get("severity") == "CRITICAL"
        ]
        if critical_findings:
            return ControlAssessmentResult(
                control_id=control_id,
                status=AssessmentStatus.FAIL,
                score=0.0,
                reason=f"Failed due to {len(critical_findings)} active critical security finding(s).",
                evidence_count=len(evidence_list),
                details={"critical_findings": critical_findings},
            )

        # 2. Check if no evidence has been ingested at all
        if not evidence_list:
            return ControlAssessmentResult(
                control_id=control_id,
                status=AssessmentStatus.NOT_ASSESSED,
                score=0.0,
                reason="No verification evidence recorded for this control.",
                evidence_count=0,
                details={"missing_evidence_types": required_types},
            )

        # 3. Analyze evidence types and freshness
        present_types = {e.get("evidence_type") for e in evidence_list}
        missing_types = [t for t in required_types if t not in present_types]

        fresh_count = 0
        stale_count = 0
        expired_count = 0

        for e in evidence_list:
            captured_at = e.get("captured_at")
            if isinstance(captured_at, str):
                captured_at = datetime.fromisoformat(captured_at)
            expires_at = e.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)

            freshness = EvidenceEngine.evaluate_freshness(
                captured_at=captured_at or now,
                evidence_type=e.get("evidence_type", ""),
                expires_at=expires_at,
                reference_time=now,
            )
            if freshness == EvidenceFreshness.FRESH:
                fresh_count += 1
            elif freshness == EvidenceFreshness.STALE:
                stale_count += 1
            elif freshness == EvidenceFreshness.EXPIRED:
                expired_count += 1

        # 4. Calculate score
        # Coverage fraction of required types (max 60 points)
        type_coverage = (
            1.0
            if not required_types
            else (len(required_types) - len(missing_types)) / len(required_types)
        )
        coverage_score = type_coverage * 60.0

        # Freshness fraction of available evidence (max 40 points)
        total_items = len(evidence_list)
        freshness_ratio = (fresh_count + (stale_count * 0.5)) / max(total_items, 1)
        freshness_score = freshness_ratio * 40.0

        raw_score = round(coverage_score + freshness_score, 1)

        # 5. Determine status
        if missing_types and len(missing_types) == len(required_types):
            status = AssessmentStatus.NOT_ASSESSED
            reason = f"Missing all required evidence types: {', '.join(missing_types)}."
        elif missing_types or stale_count > 0 or expired_count > 0:
            status = AssessmentStatus.WARN
            reasons = []
            if missing_types:
                reasons.append(f"Missing evidence types: {', '.join(missing_types)}")
            if expired_count > 0:
                reasons.append(f"{expired_count} evidence item(s) expired")
            if stale_count > 0:
                reasons.append(f"{stale_count} evidence item(s) stale")
            reason = "; ".join(reasons)
        else:
            status = AssessmentStatus.PASS
            reason = f"All {len(evidence_list)} evidence item(s) verified fresh and compliant."

        return ControlAssessmentResult(
            control_id=control_id,
            status=status,
            score=min(max(raw_score, 0.0), 100.0),
            reason=reason,
            evidence_count=len(evidence_list),
            details={
                "fresh_count": fresh_count,
                "stale_count": stale_count,
                "expired_count": expired_count,
                "missing_types": missing_types,
            },
        )

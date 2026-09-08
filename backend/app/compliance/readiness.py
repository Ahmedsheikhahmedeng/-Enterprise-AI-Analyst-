"""Compliance Readiness evaluation engine and hard blocker enforcement."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.compliance.enums import AssessmentStatus, ControlSeverity, ReadinessDecision


@dataclass(frozen=True)
class ComplianceReadinessEvaluation:
    """Readiness scorecard decision and factor analysis."""

    decision: ReadinessDecision
    composite_score: float
    framework_scores: dict[str, float]
    passed_controls: int
    warning_controls: int
    failed_controls: int
    not_assessed_controls: int
    blockers: list[str]
    warnings: list[str]
    evaluated_at: datetime


class ComplianceReadinessEvaluator:
    """Evaluates organization-wide compliance posture, weighted scores, and production deployment safety gates."""

    SEVERITY_WEIGHTS: dict[str, float] = {
        ControlSeverity.CRITICAL.value: 5.0,
        ControlSeverity.HIGH.value: 3.0,
        ControlSeverity.MEDIUM.value: 2.0,
        ControlSeverity.LOW.value: 1.0,
    }

    MANDATORY_CONTROLS: set[str] = {
        "ctrl-auth-001",
        "ctrl-rbac-001",
        "ctrl-tenant-001",
        "ctrl-tenant-002",
        "ctrl-secret-002",
        "ctrl-log-001",
    }

    @classmethod
    def evaluate_readiness(
        cls,
        assessments: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        audit_integrity_valid: bool = True,
        expired_risk_acceptances_count: int = 0,
        unprotected_exports_count: int = 0,
        reference_time: datetime | None = None,
    ) -> ComplianceReadinessEvaluation:
        """Calculate weighted composite score, detect hard blockers, and render authoritative readiness decision."""
        now = reference_time or datetime.now(UTC)

        blockers: list[str] = []
        warnings: list[str] = []

        # 1. Evaluate Assessments
        passed = 0
        warned = 0
        failed = 0
        not_assessed = 0

        weighted_earned = 0.0
        weighted_total = 0.0

        framework_tallies: dict[str, dict[str, float]] = {}

        assessment_by_id: dict[str, dict[str, Any]] = {}
        for a in assessments:
            cid = a.get("control_id", "")
            assessment_by_id[cid] = a
            status = a.get("status", AssessmentStatus.NOT_ASSESSED.value)
            score = float(a.get("score", 0.0))
            sev = a.get("severity", ControlSeverity.HIGH.value)
            fw = a.get("framework", "INTERNAL_SECURITY_BASELINE")

            weight = cls.SEVERITY_WEIGHTS.get(sev, 2.0)
            weighted_total += weight
            weighted_earned += (score / 100.0) * weight

            if fw not in framework_tallies:
                framework_tallies[fw] = {"earned": 0.0, "total": 0.0}
            framework_tallies[fw]["earned"] += (score / 100.0) * weight
            framework_tallies[fw]["total"] += weight

            if status == AssessmentStatus.PASS.value:
                passed += 1
            elif status == AssessmentStatus.WARN.value:
                warned += 1
                warnings.append(f"Control '{cid}' has warning status: {a.get('reason', '')}")
            elif status == AssessmentStatus.FAIL.value:
                failed += 1
                if cid in cls.MANDATORY_CONTROLS:
                    blockers.append(f"Hard Blocker: Mandatory control '{cid}' is in FAIL state.")
            else:
                not_assessed += 1
                if cid in cls.MANDATORY_CONTROLS:
                    warnings.append(f"Mandatory control '{cid}' has not been assessed yet.")

        # 2. Check Hard Blockers
        # A. Critical security findings
        open_criticals = [
            f
            for f in findings
            if f.get("severity") == "CRITICAL" and f.get("status") in ("OPEN", "ACKNOWLEDGED")
        ]
        if open_criticals:
            blockers.append(
                f"Hard Blocker: {len(open_criticals)} unresolved CRITICAL security finding(s) exist."
            )

        # B. Tenant Isolation checks
        tenant_1 = assessment_by_id.get("ctrl-tenant-001", {})
        tenant_2 = assessment_by_id.get("ctrl-tenant-002", {})
        if (
            tenant_1.get("status") == AssessmentStatus.FAIL.value
            or tenant_2.get("status") == AssessmentStatus.FAIL.value
        ):
            blockers.append("Hard Blocker: Tenant isolation barrier failure detected.")

        # C. Audit Integrity
        if not audit_integrity_valid:
            blockers.append("Hard Blocker: Audit log cryptographic hash chain validation failed.")

        # D. Expired risk acceptances
        if expired_risk_acceptances_count > 0:
            blockers.append(
                f"Hard Blocker: {expired_risk_acceptances_count} expired privileged risk acceptance(s)."
            )

        # E. Unprotected exports
        if unprotected_exports_count > 0:
            blockers.append(
                f"Hard Blocker: {unprotected_exports_count} unauthorized restricted export(s) flagged."
            )

        # 3. Compute Composite and Framework Scores
        composite_score = round((weighted_earned / max(weighted_total, 1.0)) * 100.0, 1)

        framework_scores = {
            fw: round((t["earned"] / max(t["total"], 1.0)) * 100.0, 1)
            for fw, t in framework_tallies.items()
        }

        # 4. Determine Readiness Decision
        if blockers or composite_score < 75.0:
            decision = ReadinessDecision.NOT_READY
        elif composite_score < 90.0 or warnings:
            decision = ReadinessDecision.READY_WITH_WARNINGS
        else:
            decision = ReadinessDecision.READY

        return ComplianceReadinessEvaluation(
            decision=decision,
            composite_score=composite_score,
            framework_scores=framework_scores,
            passed_controls=passed,
            warning_controls=warned,
            failed_controls=failed,
            not_assessed_controls=not_assessed,
            blockers=blockers,
            warnings=warnings,
            evaluated_at=now,
        )

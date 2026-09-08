"""Security Posture aggregation engine evaluating the 12 enterprise security pillars."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.compliance.enums import AssessmentStatus


@dataclass(frozen=True)
class PillarSummary:
    """Evaluation summary for a single security pillar."""

    name: str
    status: AssessmentStatus
    score: float
    controls_passed: int
    controls_total: int
    critical_findings: int
    details: dict[str, Any]


class SecurityPostureEngine:
    """Synthesizes control assessments, vulnerability findings, and operational health into the 12 security pillars."""

    PILLARS: list[str] = [
        "authentication",
        "authorization",
        "tenant_isolation",
        "secrets",
        "network_security",
        "data_security",
        "audit",
        "privacy",
        "dependencies",
        "vulnerabilities",
        "backup_security",
        "incident_status",
    ]

    CONTROL_PILLAR_MAP: dict[str, str] = {
        "ctrl-auth-001": "authentication",
        "ctrl-auth-002": "authentication",
        "ctrl-soc2-cc62": "authentication",
        "ctrl-rbac-001": "authorization",
        "ctrl-rbac-002": "authorization",
        "ctrl-soc2-cc61": "authorization",
        "ctrl-iso-a91": "authorization",
        "ctrl-tenant-001": "tenant_isolation",
        "ctrl-tenant-002": "tenant_isolation",
        "ctrl-secret-001": "secrets",
        "ctrl-secret-002": "secrets",
        "ctrl-net-001": "network_security",
        "ctrl-net-002": "network_security",
        "ctrl-data-001": "data_security",
        "ctrl-data-002": "data_security",
        "ctrl-ai-001": "data_security",
        "ctrl-ai-002": "data_security",
        "ctrl-ai-003": "data_security",
        "ctrl-log-001": "audit",
        "ctrl-log-002": "audit",
        "ctrl-priv-001": "privacy",
        "ctrl-priv-002": "privacy",
        "ctrl-soc2-cc63": "authorization",
        "ctrl-iso-a121": "incident_status",
    }

    @classmethod
    def evaluate_posture(
        cls,
        assessments: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        sre_metrics: dict[str, Any] | None = None,
        reference_time: datetime | None = None,
    ) -> dict[str, PillarSummary]:
        """Aggregate security status across all 12 defined posture pillars."""
        sre_metrics = sre_metrics or {}
        pillar_data: dict[str, dict[str, Any]] = {
            p: {"scores": [], "statuses": [], "passed": 0, "total": 0, "findings": 0}
            for p in cls.PILLARS
        }

        # 1. Map assessments to pillars
        for a in assessments:
            cid = a.get("control_id", "")
            pillar = cls.CONTROL_PILLAR_MAP.get(cid)
            if pillar and pillar in pillar_data:
                pillar_data[pillar]["total"] += 1
                score = float(a.get("score", 0.0))
                status = a.get("status", AssessmentStatus.NOT_ASSESSED.value)
                pillar_data[pillar]["scores"].append(score)
                pillar_data[pillar]["statuses"].append(status)
                if status == AssessmentStatus.PASS.value:
                    pillar_data[pillar]["passed"] += 1

        # 2. Count findings
        for f in findings:
            if f.get("status") in ("OPEN", "ACKNOWLEDGED"):
                cid = f.get("control_id")
                pillar = cls.CONTROL_PILLAR_MAP.get(cid or "", "vulnerabilities")
                if pillar in pillar_data:
                    pillar_data[pillar]["findings"] += 1

        # 3. Calculate Pillar Summaries
        results: dict[str, PillarSummary] = {}
        for pillar in cls.PILLARS:
            data = pillar_data[pillar]
            scores = data["scores"]
            statuses = data["statuses"]
            passed = data["passed"]
            total = data["total"]
            f_count = data["findings"]

            # Score calculation
            avg_score = round(sum(scores) / max(len(scores), 1), 1) if scores else 80.0

            # Determine pillar status
            if f_count > 0 and any(
                f.get("severity") == "CRITICAL" for f in findings if f.get("status") == "OPEN"
            ):
                status = AssessmentStatus.FAIL
                avg_score = min(avg_score, 40.0)
            elif AssessmentStatus.FAIL.value in statuses:
                status = AssessmentStatus.FAIL
            elif AssessmentStatus.WARN.value in statuses or f_count > 0:
                status = AssessmentStatus.WARN
            elif statuses and all(s == AssessmentStatus.PASS.value for s in statuses):
                status = AssessmentStatus.PASS
            else:
                status = (
                    AssessmentStatus.PASS
                    if pillar in ("backup_security", "dependencies")
                    else AssessmentStatus.NOT_ASSESSED
                )

            results[pillar] = PillarSummary(
                name=pillar.replace("_", " ").title(),
                status=status,
                score=avg_score,
                controls_passed=passed,
                controls_total=total,
                critical_findings=f_count,
                details={"finding_count": f_count, "metrics": sre_metrics.get(pillar, {})},
            )

        return results

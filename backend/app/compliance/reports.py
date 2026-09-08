"""Deterministic compliance report generation, versioning, and auditable digests."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class GeneratedComplianceReport:
    """Immutable, versioned compliance report representation."""

    report_id: str
    organization_id: str | None
    generated_at: str
    report_hash: str
    overall_readiness: str
    composite_score: float
    summary: dict[str, Any]
    controls_breakdown: list[dict[str, Any]]
    findings_breakdown: list[dict[str, Any]]
    risk_acceptances: list[dict[str, Any]]


class ComplianceReportGenerator:
    """Generates auditable, cryptographic JSON representations of compliance posture."""

    DISCLAIMER: str = (
        "This report provides empirical technical control readiness and evidence evaluation. "
        "It does not constitute an official SOC 2, ISO 27001, GDPR, or HIPAA certification."
    )

    @classmethod
    def generate_report(
        cls,
        organization_id: str | None,
        readiness_evaluation: dict[str, Any],
        assessments: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        risk_acceptances: list[dict[str, Any]],
    ) -> GeneratedComplianceReport:
        """Construct deterministic and hashable compliance posture report."""
        now = datetime.now(UTC).isoformat()
        report_id = f"rpt-comp-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

        payload = {
            "report_id": report_id,
            "organization_id": organization_id,
            "disclaimer": cls.DISCLAIMER,
            "readiness": readiness_evaluation,
            "assessments_count": len(assessments),
            "findings_count": len(findings),
            "risk_acceptances_count": len(risk_acceptances),
        }

        serialized = json.dumps(payload, sort_keys=True)
        report_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        return GeneratedComplianceReport(
            report_id=report_id,
            organization_id=organization_id,
            generated_at=now,
            report_hash=report_hash,
            overall_readiness=readiness_evaluation.get("decision", "NOT_READY"),
            composite_score=float(readiness_evaluation.get("composite_score", 0.0)),
            summary=payload,
            controls_breakdown=assessments,
            findings_breakdown=findings,
            risk_acceptances=risk_acceptances,
        )

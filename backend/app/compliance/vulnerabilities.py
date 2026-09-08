"""Vulnerability source ingestion abstraction mapping scanner reports to unified SecurityFindings."""

from dataclasses import dataclass
from typing import Any

from app.compliance.enums import FindingSeverity


@dataclass(frozen=True)
class IngestedFinding:
    """Normalized finding generated from an external static analysis or vulnerability scanner."""

    title: str
    description: str
    severity: FindingSeverity
    source: str
    details: dict[str, Any]
    control_id: str | None = None


class VulnerabilityIngestionEngine:
    """Parses outputs from Bandit, pip-audit, npm audit, Trivy, and Gitleaks into unified finding models."""

    @classmethod
    def parse_bandit_report(cls, report: dict[str, Any]) -> list[IngestedFinding]:
        """Convert Bandit Python AST security scanner JSON to standardized findings."""
        findings = []
        for result in report.get("results", []):
            sev_raw = result.get("issue_severity", "MEDIUM").upper()
            sev = (
                FindingSeverity.HIGH
                if sev_raw == "HIGH"
                else FindingSeverity.MEDIUM
                if sev_raw == "MEDIUM"
                else FindingSeverity.LOW
            )
            findings.append(
                IngestedFinding(
                    title=f"Bandit: {result.get('test_name', 'Security Issue')} in {result.get('filename', 'unknown')}:{result.get('line_number', 0)}",
                    description=result.get("issue_text", "No details provided"),
                    severity=sev,
                    source="Bandit",
                    control_id="ctrl-data-001",
                    details=result,
                )
            )
        return findings

    @classmethod
    def parse_pip_audit_report(cls, report: dict[str, Any]) -> list[IngestedFinding]:
        """Convert pip-audit dependency scanner JSON to standardized findings."""
        findings = []
        for dep in report.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                findings.append(
                    IngestedFinding(
                        title=f"Vulnerable Dependency: {dep.get('name')}=={dep.get('version')} ({vuln.get('id')})",
                        description=vuln.get("description", "Vulnerability detected in package."),
                        severity=FindingSeverity.HIGH,
                        source="pip-audit",
                        control_id="ctrl-secret-002",
                        details=vuln,
                    )
                )
        return findings

    @classmethod
    def parse_gitleaks_report(cls, report: list[dict[str, Any]]) -> list[IngestedFinding]:
        """Convert Gitleaks secret detection scanner JSON to standardized findings."""
        findings = []
        for leak in report:
            findings.append(
                IngestedFinding(
                    title=f"Hardcoded Secret Detected: {leak.get('RuleID')} in {leak.get('File')}",
                    description=leak.get(
                        "Description", "Potential credential committed to source control."
                    ),
                    severity=FindingSeverity.CRITICAL,
                    source="Gitleaks",
                    control_id="ctrl-secret-002",
                    details={
                        "file": leak.get("File"),
                        "line": leak.get("StartLine"),
                        "commit": leak.get("Commit"),
                    },
                )
            )
        return findings

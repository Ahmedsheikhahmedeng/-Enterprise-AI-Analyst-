"""Unit tests for Security Findings normalization and external scanner ingestion."""

from app.compliance.enums import FindingSeverity
from app.compliance.vulnerabilities import VulnerabilityIngestionEngine


def test_bandit_report_ingestion() -> None:
    report = {
        "results": [
            {
                "test_name": "hardcoded_tmp_directory",
                "filename": "backend/app/temp.py",
                "line_number": 42,
                "issue_severity": "MEDIUM",
                "issue_text": "Probable insecure usage of temp directory",
            }
        ]
    }
    findings = VulnerabilityIngestionEngine.parse_bandit_report(report)
    assert len(findings) == 1
    assert findings[0].source == "Bandit"
    assert findings[0].severity == FindingSeverity.MEDIUM
    assert "temp.py:42" in findings[0].title


def test_gitleaks_report_ingestion() -> None:
    report = [
        {
            "RuleID": "aws-access-token",
            "File": "config/keys.json",
            "StartLine": 14,
            "Commit": "a1b2c3d",
            "Description": "AWS Access Key ID identified in git commit",
        }
    ]
    findings = VulnerabilityIngestionEngine.parse_gitleaks_report(report)
    assert len(findings) == 1
    assert findings[0].source == "Gitleaks"
    assert findings[0].severity == FindingSeverity.CRITICAL
    assert "keys.json" in findings[0].title

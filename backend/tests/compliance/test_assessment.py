"""Unit tests for compliance control assessment calculations and status determination."""

from datetime import UTC, datetime, timedelta

from app.compliance.assessor import ComplianceAssessor
from app.compliance.enums import AssessmentStatus


def test_assess_control_no_evidence() -> None:
    res = ComplianceAssessor.assess_control(
        control_id="ctrl-auth-001",
        evidence_list=[],
    )
    assert res.status == AssessmentStatus.NOT_ASSESSED
    assert res.score == 0.0
    assert "No verification evidence" in res.reason


def test_assess_control_all_evidence_fresh_passes() -> None:
    now = datetime.now(UTC)
    evidence = [
        {
            "evidence_type": "SECURITY_TEST",
            "captured_at": now - timedelta(days=2),
            "source": "pytest",
        },
        {
            "evidence_type": "CONFIGURATION",
            "captured_at": now - timedelta(days=5),
            "source": "auth_settings",
        },
    ]
    res = ComplianceAssessor.assess_control(
        control_id="ctrl-auth-001",
        evidence_list=evidence,
        reference_time=now,
    )
    assert res.status == AssessmentStatus.PASS
    assert res.score == 100.0
    assert "compliant" in res.reason


def test_assess_control_missing_required_evidence_warns() -> None:
    now = datetime.now(UTC)
    evidence = [
        {
            "evidence_type": "CONFIGURATION",
            "captured_at": now - timedelta(days=5),
            "source": "auth_settings",
        },
    ]
    res = ComplianceAssessor.assess_control(
        control_id="ctrl-auth-001",  # Requires SECURITY_TEST and CONFIGURATION
        evidence_list=evidence,
        reference_time=now,
    )
    assert res.status == AssessmentStatus.WARN
    assert res.score < 100.0
    assert "Missing evidence types" in res.reason


def test_assess_control_expired_evidence_warns() -> None:
    now = datetime.now(UTC)
    evidence = [
        {
            "evidence_type": "SECURITY_TEST",
            "captured_at": now - timedelta(days=30),
            "expires_at": now - timedelta(days=1),
            "source": "pytest",
        },
        {
            "evidence_type": "CONFIGURATION",
            "captured_at": now - timedelta(days=5),
            "source": "auth_settings",
        },
    ]
    res = ComplianceAssessor.assess_control(
        control_id="ctrl-auth-001",
        evidence_list=evidence,
        reference_time=now,
    )
    assert res.status == AssessmentStatus.WARN
    assert "expired" in res.reason


def test_assess_control_critical_finding_fails() -> None:
    now = datetime.now(UTC)
    evidence = [
        {"evidence_type": "SECURITY_TEST", "captured_at": now, "source": "pytest"},
        {"evidence_type": "CONFIGURATION", "captured_at": now, "source": "auth_settings"},
    ]
    findings = [{"control_id": "ctrl-auth-001", "severity": "CRITICAL", "status": "OPEN"}]
    res = ComplianceAssessor.assess_control(
        control_id="ctrl-auth-001",
        evidence_list=evidence,
        active_findings=findings,
        reference_time=now,
    )
    assert res.status == AssessmentStatus.FAIL
    assert res.score == 0.0
    assert "Failed due to 1 active critical security finding" in res.reason

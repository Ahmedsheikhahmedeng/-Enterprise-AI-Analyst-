"""Unit tests for Compliance Readiness evaluation and hard blocker enforcement."""

from app.compliance.enums import AssessmentStatus, ControlSeverity, ReadinessDecision
from app.compliance.readiness import ComplianceReadinessEvaluator


def test_readiness_all_controls_pass_is_ready() -> None:
    assessments = [
        {
            "control_id": "ctrl-auth-001",
            "status": AssessmentStatus.PASS.value,
            "score": 100.0,
            "severity": ControlSeverity.CRITICAL.value,
        },
        {
            "control_id": "ctrl-rbac-001",
            "status": AssessmentStatus.PASS.value,
            "score": 100.0,
            "severity": ControlSeverity.CRITICAL.value,
        },
        {
            "control_id": "ctrl-tenant-001",
            "status": AssessmentStatus.PASS.value,
            "score": 100.0,
            "severity": ControlSeverity.CRITICAL.value,
        },
        {
            "control_id": "ctrl-tenant-002",
            "status": AssessmentStatus.PASS.value,
            "score": 100.0,
            "severity": ControlSeverity.CRITICAL.value,
        },
        {
            "control_id": "ctrl-secret-002",
            "status": AssessmentStatus.PASS.value,
            "score": 100.0,
            "severity": ControlSeverity.CRITICAL.value,
        },
        {
            "control_id": "ctrl-log-001",
            "status": AssessmentStatus.PASS.value,
            "score": 100.0,
            "severity": ControlSeverity.HIGH.value,
        },
    ]
    evaluation = ComplianceReadinessEvaluator.evaluate_readiness(
        assessments=assessments,
        findings=[],
        audit_integrity_valid=True,
    )
    assert evaluation.decision == ReadinessDecision.READY
    assert evaluation.composite_score == 100.0
    assert len(evaluation.blockers) == 0


def test_readiness_critical_finding_hard_blocker() -> None:
    assessments = [
        {
            "control_id": "ctrl-auth-001",
            "status": AssessmentStatus.PASS.value,
            "score": 100.0,
            "severity": ControlSeverity.CRITICAL.value,
        },
    ]
    findings = [{"id": "f-1", "severity": "CRITICAL", "status": "OPEN"}]

    evaluation = ComplianceReadinessEvaluator.evaluate_readiness(
        assessments=assessments,
        findings=findings,
    )
    assert evaluation.decision == ReadinessDecision.NOT_READY
    assert any("CRITICAL security finding" in b for b in evaluation.blockers)


def test_readiness_tenant_isolation_failure_hard_blocker() -> None:
    assessments = [
        {
            "control_id": "ctrl-tenant-001",
            "status": AssessmentStatus.FAIL.value,
            "score": 0.0,
            "severity": ControlSeverity.CRITICAL.value,
        },
    ]
    evaluation = ComplianceReadinessEvaluator.evaluate_readiness(
        assessments=assessments,
        findings=[],
    )
    assert evaluation.decision == ReadinessDecision.NOT_READY
    assert any("Tenant isolation barrier failure" in b for b in evaluation.blockers)


def test_readiness_audit_integrity_failure_hard_blocker() -> None:
    assessments = [
        {
            "control_id": "ctrl-log-001",
            "status": AssessmentStatus.PASS.value,
            "score": 100.0,
            "severity": ControlSeverity.HIGH.value,
        },
    ]
    evaluation = ComplianceReadinessEvaluator.evaluate_readiness(
        assessments=assessments,
        findings=[],
        audit_integrity_valid=False,
    )
    assert evaluation.decision == ReadinessDecision.NOT_READY
    assert any(
        "Audit log cryptographic hash chain validation failed" in b for b in evaluation.blockers
    )

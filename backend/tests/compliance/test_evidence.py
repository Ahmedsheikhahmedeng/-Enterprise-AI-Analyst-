"""Unit tests for evidence hashing, versioning, and freshness checks."""

from datetime import UTC, datetime, timedelta

from app.compliance.enums import EvidenceFreshness, EvidenceType
from app.compliance.evidence import EvidenceEngine


def test_evidence_hash_determinism() -> None:
    now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=UTC)
    hash_1 = EvidenceEngine.compute_evidence_hash(
        control_id="ctrl-auth-001",
        evidence_type=EvidenceType.SECURITY_TEST.value,
        source="pytest_suite",
        reference="tests/security/test_auth_security.py",
        metadata_payload={"tests_passed": 12},
        captured_at=now,
    )
    hash_2 = EvidenceEngine.compute_evidence_hash(
        control_id="ctrl-auth-001",
        evidence_type=EvidenceType.SECURITY_TEST.value,
        source="pytest_suite",
        reference="tests/security/test_auth_security.py",
        metadata_payload={"tests_passed": 12},
        captured_at=now,
    )
    assert hash_1 == hash_2
    assert len(hash_1) == 64  # SHA-256 hex string


def test_evidence_freshness_evaluation() -> None:
    now = datetime.now(UTC)

    # Fresh evidence (3 days old)
    fresh = EvidenceEngine.evaluate_freshness(
        captured_at=now - timedelta(days=3),
        evidence_type=EvidenceType.SECURITY_TEST.value,
        reference_time=now,
    )
    assert fresh == EvidenceFreshness.FRESH

    # Stale evidence (20 days old, max is 14 for security test)
    stale = EvidenceEngine.evaluate_freshness(
        captured_at=now - timedelta(days=20),
        evidence_type=EvidenceType.SECURITY_TEST.value,
        reference_time=now,
    )
    assert stale == EvidenceFreshness.STALE

    # Explicitly expired
    expired = EvidenceEngine.evaluate_freshness(
        captured_at=now - timedelta(days=5),
        evidence_type=EvidenceType.SECURITY_TEST.value,
        expires_at=now - timedelta(hours=1),
        reference_time=now,
    )
    assert expired == EvidenceFreshness.EXPIRED

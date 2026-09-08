"""Unit tests for cryptographic audit hash chain validation and tamper detection."""

from app.compliance.audit_integrity import AuditIntegrityVerifier
from app.compliance.enums import AuditIntegrityStatus


def test_audit_integrity_valid_chain() -> None:
    org_id = "org-test-123"
    events = [
        {
            "id": "ev-1",
            "user_id": "u-1",
            "action": "LOGIN",
            "resource_type": "USER",
            "resource_id": "u-1",
            "created_at": "2026-09-07T10:00:00Z",
        },
        {
            "id": "ev-2",
            "user_id": "u-1",
            "action": "CREATE_DOCUMENT",
            "resource_type": "DOCUMENT",
            "resource_id": "d-1",
            "created_at": "2026-09-07T10:05:00Z",
        },
        {
            "id": "ev-3",
            "user_id": "u-2",
            "action": "UPDATE_POLICY",
            "resource_type": "POLICY",
            "resource_id": "p-1",
            "created_at": "2026-09-07T10:10:00Z",
        },
    ]

    res = AuditIntegrityVerifier.verify_ledger(org_id, events)
    assert res.status == AuditIntegrityStatus.VALID
    assert res.total_records_checked == 3
    assert res.first_tampered_record_id is None
    assert res.latest_block_hash is not None


def test_audit_integrity_empty_ledger() -> None:
    res = AuditIntegrityVerifier.verify_ledger("org-empty", [])
    assert res.status == AuditIntegrityStatus.INCOMPLETE
    assert res.total_records_checked == 0


def test_audit_integrity_tampered_metadata_hash() -> None:
    org_id = "org-tamper"
    events = [
        {
            "id": "ev-1",
            "user_id": "u-1",
            "action": "LOGIN",
            "resource_type": "USER",
            "resource_id": "u-1",
            "created_at": "2026-09-07T10:00:00Z",
            "metadata": {"chain_hash": "corrupted_hash"},
        },
    ]
    res = AuditIntegrityVerifier.verify_ledger(org_id, events)
    assert res.status == AuditIntegrityStatus.INVALID
    assert res.first_tampered_record_id == "ev-1"
    assert "mismatch" in res.reason

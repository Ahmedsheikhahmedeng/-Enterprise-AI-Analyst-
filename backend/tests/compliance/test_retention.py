"""Unit tests for retention schedules and expiration calculations."""

from datetime import UTC, datetime, timedelta

from app.compliance.enums import RetentionResourceType
from app.compliance.retention import RetentionEngine


def test_retention_expiration_calculation() -> None:
    created_at = datetime(2025, 1, 1, tzinfo=UTC)
    expires_at = RetentionEngine.calculate_expiration(created_at, 90)
    assert expires_at == created_at + timedelta(days=90)


def test_retention_unexpired_record() -> None:
    now = datetime.now(UTC)
    recent_date = now - timedelta(days=10)
    res = RetentionEngine.evaluate_resource_retention(
        resource_id="doc-123",
        resource_type=RetentionResourceType.DOCUMENTS.value,
        created_at=recent_date,
        retention_days=30,
        reference_time=now,
    )
    assert res.is_expired is False
    assert res.eligible_for_deletion is False
    assert "remaining" in res.reason


def test_retention_expired_record_marked_eligible_without_deletion() -> None:
    now = datetime.now(UTC)
    old_date = now - timedelta(days=100)
    res = RetentionEngine.evaluate_resource_retention(
        resource_id="doc-123",
        resource_type=RetentionResourceType.DOCUMENTS.value,
        created_at=old_date,
        retention_days=30,
        reference_time=now,
    )
    assert res.is_expired is True
    assert res.eligible_for_deletion is True
    assert "Eligible for explicit deletion" in res.reason

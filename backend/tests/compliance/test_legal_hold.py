"""Unit tests for Legal Hold overrides and deletion eligibility freezing."""

from datetime import UTC, datetime, timedelta

from app.compliance.enums import RetentionResourceType
from app.compliance.retention import RetentionEngine


def test_legal_hold_freezes_expired_record_deletion() -> None:
    now = datetime.now(UTC)
    old_date = now - timedelta(days=200)

    # Without legal hold -> eligible for deletion
    normal_res = RetentionEngine.evaluate_resource_retention(
        resource_id="dataset-sec-audit",
        resource_type=RetentionResourceType.DATASETS.value,
        created_at=old_date,
        retention_days=90,
        active_legal_holds=[],
        reference_time=now,
    )
    assert normal_res.is_expired is True
    assert normal_res.eligible_for_deletion is True

    # With specific resource legal hold -> frozen
    holds = [{"name": "Litigation 2026", "active": True, "resources": ["dataset-sec-audit"]}]
    held_res = RetentionEngine.evaluate_resource_retention(
        resource_id="dataset-sec-audit",
        resource_type=RetentionResourceType.DATASETS.value,
        created_at=old_date,
        retention_days=90,
        active_legal_holds=holds,
        reference_time=now,
    )
    assert held_res.is_expired is True
    assert held_res.is_under_legal_hold is True
    assert held_res.eligible_for_deletion is False
    assert "Deletion frozen by active legal hold(s)" in held_res.reason


def test_wildcard_legal_hold_freezes_all_resources() -> None:
    now = datetime.now(UTC)
    holds = [{"name": "Global Preservation", "active": True, "resources": ["*"]}]

    res = RetentionEngine.evaluate_resource_retention(
        resource_id="any-doc-id",
        resource_type=RetentionResourceType.DOCUMENTS.value,
        created_at=now - timedelta(days=500),
        retention_days=30,
        active_legal_holds=holds,
        reference_time=now,
    )
    assert res.is_under_legal_hold is True
    assert res.eligible_for_deletion is False

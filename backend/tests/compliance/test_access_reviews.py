"""Unit tests for Access Review analysis and inactive user detection."""

from datetime import UTC, datetime, timedelta

from app.compliance.access_reviews import AccessReviewEngine
from app.compliance.enums import AccessReviewStatus


def test_inactive_user_detection_over_90_days() -> None:
    now = datetime.now(UTC)
    last_login = now - timedelta(days=95)

    item = AccessReviewEngine.evaluate_user_access(
        user_id="usr-1",
        user_email="inactive@enterprise.com",
        role="Viewer",
        permissions=["documents.read"],
        last_activity_at=last_login,
        reference_time=now,
    )
    assert item.is_inactive is True
    assert item.review_status == AccessReviewStatus.REVOKE_RECOMMENDED
    assert "Inactive for 95 days" in item.recommendation


def test_never_logged_in_user_flagged() -> None:
    now = datetime.now(UTC)
    item = AccessReviewEngine.evaluate_user_access(
        user_id="usr-2",
        user_email="ghost@enterprise.com",
        role="Analyst",
        permissions=["documents.read"],
        last_activity_at=None,
        reference_time=now,
    )
    assert item.is_inactive is True
    assert item.review_status == AccessReviewStatus.REVOKE_RECOMMENDED
    assert "never logged in" in item.recommendation


def test_active_privileged_user_confirmed() -> None:
    now = datetime.now(UTC)
    item = AccessReviewEngine.evaluate_user_access(
        user_id="usr-3",
        user_email="secadmin@enterprise.com",
        role="Admin",
        permissions=["admin.all"],
        last_activity_at=now - timedelta(hours=2),
        reference_time=now,
    )
    assert item.is_inactive is False
    assert item.is_privileged is True
    assert item.review_status == AccessReviewStatus.CONFIRMED

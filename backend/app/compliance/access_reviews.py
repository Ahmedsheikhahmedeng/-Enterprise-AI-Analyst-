"""Access review analysis, inactive account identification, and privilege governance."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.compliance.enums import AccessReviewStatus


@dataclass(frozen=True)
class EvaluatedAccessItem:
    """Evaluation result for an individual user's access within an access review."""

    user_id: str
    user_email: str
    role: str
    permissions: list[str]
    last_activity_at: datetime | None
    is_inactive: bool
    is_privileged: bool
    recommendation: str
    review_status: AccessReviewStatus


class AccessReviewEngine:
    """Analyzes user activity, role distributions, and excessive permissions to generate access review recommendations."""

    INACTIVE_THRESHOLD_DAYS: int = 90
    PRIVILEGED_ROLES: set[str] = {"Admin", "SuperAdmin", "SecurityAdmin", "ComplianceAdmin"}

    @classmethod
    def evaluate_user_access(
        cls,
        user_id: str,
        user_email: str,
        role: str,
        permissions: list[str],
        last_activity_at: datetime | None,
        reference_time: datetime | None = None,
    ) -> EvaluatedAccessItem:
        """Analyze a user's role, permissions, and activity timeline."""
        now = reference_time or datetime.now(UTC)
        is_privileged = role in cls.PRIVILEGED_ROLES

        if last_activity_at is None:
            is_inactive = True
            rec = "REVOKE_RECOMMENDED: Account has never logged in."
            status = AccessReviewStatus.REVOKE_RECOMMENDED
        else:
            inactivity_duration = now - last_activity_at
            if inactivity_duration > timedelta(days=cls.INACTIVE_THRESHOLD_DAYS):
                is_inactive = True
                rec = f"REVOKE_RECOMMENDED: Inactive for {inactivity_duration.days} days."
                status = AccessReviewStatus.REVOKE_RECOMMENDED
            elif is_privileged:
                is_inactive = False
                rec = "CONFIRMED: Active privileged account verified."
                status = AccessReviewStatus.CONFIRMED
            else:
                is_inactive = False
                rec = "CONFIRMED: Regular user activity within normal parameters."
                status = AccessReviewStatus.CONFIRMED

        return EvaluatedAccessItem(
            user_id=user_id,
            user_email=user_email,
            role=role,
            permissions=permissions,
            last_activity_at=last_activity_at,
            is_inactive=is_inactive,
            is_privileged=is_privileged,
            recommendation=rec,
            review_status=status,
        )

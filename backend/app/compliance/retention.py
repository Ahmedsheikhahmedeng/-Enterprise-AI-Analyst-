"""Data Retention engine, expiration calculations, and Legal Hold safeguards."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.compliance.enums import RetentionResourceType


@dataclass(frozen=True)
class ExpirationCheckResult:
    """Retention evaluation outcome for a specific resource record."""

    resource_id: str
    resource_type: str
    created_at: datetime
    expires_at: datetime
    is_expired: bool
    is_under_legal_hold: bool
    eligible_for_deletion: bool
    reason: str


class RetentionEngine:
    """Calculates resource expiration schedules and enforces legal hold exemptions without destructive auto-deletion."""

    DEFAULT_RETENTION_DAYS: dict[str, int] = {
        RetentionResourceType.DOCUMENTS.value: 365,
        RetentionResourceType.DATASETS.value: 365,
        RetentionResourceType.MEMORY.value: 90,
        RetentionResourceType.AUDIT_EVENTS.value: 730,
        RetentionResourceType.SECURITY_EVENTS.value: 730,
        RetentionResourceType.INCIDENTS.value: 365,
        RetentionResourceType.REPORTS.value: 365,
        RetentionResourceType.EVIDENCE.value: 365,
    }

    @classmethod
    def calculate_expiration(cls, created_at: datetime, retention_days: int) -> datetime:
        """Calculate absolute expiration timestamp from creation date."""
        return created_at + timedelta(days=retention_days)

    @classmethod
    def evaluate_resource_retention(
        cls,
        resource_id: str,
        resource_type: str,
        created_at: datetime,
        retention_days: int | None = None,
        active_legal_holds: list[dict[str, Any]] | None = None,
        reference_time: datetime | None = None,
    ) -> ExpirationCheckResult:
        """Assess whether a record has exceeded retention and whether legal holds freeze its deletion eligibility."""
        now = reference_time or datetime.now(UTC)
        days = retention_days or cls.DEFAULT_RETENTION_DAYS.get(resource_type, 365)
        expires_at = cls.calculate_expiration(created_at, days)
        is_expired = now >= expires_at

        # Check for active legal holds
        active_holds = active_legal_holds or []
        is_held = False
        hold_names = []
        for hold in active_holds:
            if hold.get("active", True):
                held_resources = hold.get("resources", [])
                # Either explicit resource ID, wildcard "*", or resource type match
                if (
                    "*" in held_resources
                    or resource_id in held_resources
                    or resource_type in held_resources
                ):
                    is_held = True
                    hold_names.append(hold.get("name", "Unnamed Hold"))

        if is_held:
            eligible = False
            reason = f"Deletion frozen by active legal hold(s): {', '.join(hold_names)}."
        elif is_expired:
            eligible = True
            reason = f"Retention period ({days} days) elapsed on {expires_at.date()}. Eligible for explicit deletion."
        else:
            eligible = False
            days_left = (expires_at - now).days
            reason = f"Active retention. {days_left} days remaining until expiration."

        return ExpirationCheckResult(
            resource_id=resource_id,
            resource_type=resource_type,
            created_at=created_at,
            expires_at=expires_at,
            is_expired=is_expired,
            is_under_legal_hold=is_held,
            eligible_for_deletion=eligible,
            reason=reason,
        )

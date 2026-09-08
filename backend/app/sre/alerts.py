"""Alert lifecycle management: deterministic fingerprinting, deduplication, grouping, suppression, and noise calculation."""

import hashlib
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from app.sre.enums import AlertSeverityEnum
from app.sre.schemas import AlertNoiseResponse


def generate_alert_fingerprint(
    organization_id: uuid.UUID | None,
    service: str,
    metric: str,
    rule_or_name: str,
    severity: str,
) -> str:
    """Generate a deterministic, stable SHA-256 fingerprint for an alert.

    Invariants:
    - Independent of timestamps to ensure identical events match.
    - Scoped by organization, service, metric, rule name, and severity.
    """
    org_str = str(organization_id) if organization_id else "global"
    raw = f"{org_str}:{service.lower()}:{metric.lower()}:{rule_or_name.lower()}:{severity.upper()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def should_suppress_alert(
    severity: str,
    service: str,
    active_maintenance_windows: Sequence[tuple[str | None, datetime, datetime]],
    now: datetime | None = None,
) -> tuple[bool, str | None]:
    """Evaluate whether an alert should be suppressed.

    Rules:
    - CRITICAL security alerts are NEVER suppressed automatically during routine maintenance.
    - If now falls within an active maintenance window for this service (or platform-wide None), suppress.
    """
    now = now or datetime.now(UTC)

    # CRITICAL alerts cannot be suppressed by generic maintenance windows
    if severity.upper() == AlertSeverityEnum.CRITICAL.value:
        return False, None

    for maint_service, starts_at, ends_at in active_maintenance_windows:
        if starts_at <= now <= ends_at and (
            maint_service is None or maint_service.lower() == service.lower()
        ):
            return (
                True,
                f"Suppressed due to active maintenance window ({starts_at.isoformat()} to {ends_at.isoformat()})",
            )

    return False, None


def calculate_alert_noise_ratio(
    total_alerts: int,
    total_occurrences: int,
    unique_fingerprints: int,
) -> AlertNoiseResponse:
    """Calculate deduplication and noise ratio.

    Formula:
    - duplicate_alerts = total_occurrences - total_alerts
    - noise_ratio = duplicate_alerts / total_occurrences (if total_occurrences > 0 else 0.0)
    - Classification: LOW (< 0.20), MEDIUM (0.20-0.50), HIGH (> 0.50)
    """
    duplicate_count = max(0, total_occurrences - total_alerts)
    if total_occurrences > 0:
        ratio = max(0.0, min(1.0, duplicate_count / total_occurrences))
    else:
        ratio = 0.0

    if ratio > 0.50:
        level = "HIGH"
    elif ratio >= 0.20:
        level = "MEDIUM"
    else:
        level = "LOW"

    return AlertNoiseResponse(
        total_alerts=total_alerts,
        duplicate_alerts=duplicate_count,
        unique_fingerprints=unique_fingerprints,
        noise_ratio=round(ratio, 4),
        noise_level=level,
    )

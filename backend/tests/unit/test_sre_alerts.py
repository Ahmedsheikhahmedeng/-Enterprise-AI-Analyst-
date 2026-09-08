"""Unit tests for Alert fingerprinting, suppression policies, and noise calculations."""

import uuid
from datetime import UTC, datetime, timedelta

from app.sre.alerts import (
    calculate_alert_noise_ratio,
    generate_alert_fingerprint,
    should_suppress_alert,
)
from app.sre.enums import AlertSeverityEnum


class TestAlertFingerprinting:
    """Validate stability and collision-resistance of deterministic alert fingerprints."""

    def test_fingerprint_determinism(self) -> None:
        org_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
        fp1 = generate_alert_fingerprint(
            organization_id=org_id,
            service="database",
            metric="POOL_UTILIZATION",
            rule_or_name="High PostgreSQL Latency",
            severity="WARNING",
        )
        fp2 = generate_alert_fingerprint(
            organization_id=org_id,
            service="database",
            metric="POOL_UTILIZATION",
            rule_or_name="High PostgreSQL Latency",
            severity="WARNING",
        )
        assert fp1 == fp2
        assert len(fp1) == 64  # Valid SHA-256 hex string

    def test_fingerprint_case_insensitivity(self) -> None:
        org_id = uuid.uuid4()
        fp_lower = generate_alert_fingerprint(org_id, "api", "latency", "rule1", "warning")
        fp_upper = generate_alert_fingerprint(org_id, "API", "LATENCY", "RULE1", "WARNING")
        assert fp_lower == fp_upper

    def test_fingerprint_dimension_sensitivity(self) -> None:
        org_id = uuid.uuid4()
        fp_warn = generate_alert_fingerprint(org_id, "api", "latency", "rule1", "WARNING")
        fp_crit = generate_alert_fingerprint(org_id, "api", "latency", "rule1", "CRITICAL")
        assert fp_warn != fp_crit


class TestAlertSuppression:
    """Validate maintenance window suppression and security critical exemptions."""

    def test_maintenance_window_suppresses_routine_alert(self) -> None:
        now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=UTC)
        maint_windows = [
            ("database", now - timedelta(hours=1), now + timedelta(hours=1)),
        ]

        # Routine warning for database service during maintenance -> suppressed
        suppressed, reason = should_suppress_alert(
            severity=AlertSeverityEnum.WARNING.value,
            service="database",
            active_maintenance_windows=maint_windows,
            now=now,
        )
        assert suppressed is True
        assert reason is not None
        assert "active maintenance window" in reason

    def test_maintenance_window_unmatched_service_not_suppressed(self) -> None:
        now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=UTC)
        maint_windows = [
            ("database", now - timedelta(hours=1), now + timedelta(hours=1)),
        ]

        # Routine warning for redis service while database is in maintenance -> NOT suppressed
        suppressed, reason = should_suppress_alert(
            severity=AlertSeverityEnum.WARNING.value,
            service="redis",
            active_maintenance_windows=maint_windows,
            now=now,
        )
        assert suppressed is False
        assert reason is None

    def test_critical_security_alert_exemption(self) -> None:
        now = datetime(2026, 9, 7, 12, 0, 0, tzinfo=UTC)
        maint_windows = [
            ("database", now - timedelta(hours=1), now + timedelta(hours=1)),
        ]

        # CRITICAL severity alerts MUST NOT be suppressed automatically
        suppressed, reason = should_suppress_alert(
            severity=AlertSeverityEnum.CRITICAL.value,
            service="database",
            active_maintenance_windows=maint_windows,
            now=now,
        )
        assert suppressed is False


class TestAlertNoiseRatio:
    """Validate noise ratio calculation and classification thresholds."""

    def test_low_noise_calculation(self) -> None:
        # 100 occurrences of 90 alerts -> 10 duplicates -> 10% noise (LOW)
        noise = calculate_alert_noise_ratio(
            total_alerts=90, total_occurrences=100, unique_fingerprints=90
        )
        assert noise.noise_ratio == 0.10
        assert noise.noise_level == "LOW"

    def test_high_noise_storm_calculation(self) -> None:
        # 1000 occurrences of 100 alerts -> 900 duplicates -> 90% noise (HIGH)
        noise = calculate_alert_noise_ratio(
            total_alerts=100, total_occurrences=1000, unique_fingerprints=100
        )
        assert noise.noise_ratio == 0.90
        assert noise.noise_level == "HIGH"
        assert noise.duplicate_alerts == 900

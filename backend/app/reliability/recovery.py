"""Recovery validation and empirical time measurement (MTTD, MTTA, MTTR, Time-to-Recovery)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class RecoveryTimeline:
    """Timeline milestones for a single chaos scenario run."""

    injected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    detected_at: datetime | None = None
    acknowledged_at: datetime | None = None
    mitigated_at: datetime | None = None
    recovered_at: datetime | None = None
    resolved_at: datetime | None = None

    def mark_detected(self) -> None:
        if not self.detected_at:
            self.detected_at = datetime.now(UTC)

    def mark_acknowledged(self) -> None:
        if not self.acknowledged_at:
            self.acknowledged_at = datetime.now(UTC)

    def mark_mitigated(self) -> None:
        if not self.mitigated_at:
            self.mitigated_at = datetime.now(UTC)

    def mark_recovered(self) -> None:
        if not self.recovered_at:
            self.recovered_at = datetime.now(UTC)

    def mark_resolved(self) -> None:
        if not self.resolved_at:
            self.resolved_at = datetime.now(UTC)

    @property
    def mttd_seconds(self) -> float | None:
        """Mean Time to Detect (injected_at -> detected_at)."""
        if self.detected_at and self.injected_at:
            return max(0.0, (self.detected_at - self.injected_at).total_seconds())
        return None

    @property
    def mtta_seconds(self) -> float | None:
        """Mean Time to Acknowledge (detected_at -> acknowledged_at)."""
        if self.acknowledged_at and self.detected_at:
            return max(0.0, (self.acknowledged_at - self.detected_at).total_seconds())
        return None

    @property
    def mttr_seconds(self) -> float | None:
        """Mean Time to Resolve (detected_at -> resolved_at)."""
        if self.resolved_at and self.detected_at:
            return max(0.0, (self.resolved_at - self.detected_at).total_seconds())
        return None

    @property
    def time_to_recovery_seconds(self) -> float | None:
        """Infrastructure / Component restoration time (injected_at -> recovered_at)."""
        if self.recovered_at and self.injected_at:
            return max(0.0, (self.recovered_at - self.injected_at).total_seconds())
        return None


class RecoveryValidator:
    """Validates that a degraded component or dependency cleanly recovers."""

    @staticmethod
    def evaluate_dependency_recovery(
        pre_fault_state: str,
        in_fault_state: str,
        post_fault_state: str,
    ) -> dict[str, Any]:
        """Verify state transitions: HEALTHY -> DEGRADED/UNHEALTHY -> HEALTHY."""
        degraded = in_fault_state in ("DEGRADED", "UNHEALTHY")
        restored = post_fault_state == "HEALTHY"
        successful = degraded and restored
        return {
            "pre_fault_state": pre_fault_state,
            "in_fault_state": in_fault_state,
            "post_fault_state": post_fault_state,
            "fault_detected": degraded,
            "fully_restored": restored,
            "recovery_successful": successful,
        }

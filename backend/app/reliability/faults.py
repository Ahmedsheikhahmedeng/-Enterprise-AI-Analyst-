"""Fault definitions and configurations for deterministic chaos injection."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.reliability.enums import FaultType, InjectorLifecycle


@dataclass
class FaultConfig:
    """Configuration for a specific fault injection."""

    fault_type: FaultType
    target: str = "default"
    latency_ms: float = 0.0
    error_code: int = 500
    error_rate: float = 1.0  # 0.0 to 1.0
    duration_seconds: float = 30.0
    parameters: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate boundaries of fault parameters."""
        if self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        if not (0.0 <= self.error_rate <= 1.0):
            raise ValueError("error_rate must be between 0.0 and 1.0")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be strictly positive")


@dataclass
class FaultContext:
    """Runtime context tracking active fault lifecycle."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    fault_type: FaultType = FaultType.POSTGRES_UNAVAILABLE
    lifecycle: InjectorLifecycle = InjectorLifecycle.IDLE
    injected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    recovered_at: datetime | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def mark_active(self, details: dict[str, Any] | None = None) -> None:
        """Transition injector to ACTIVE state."""
        self.lifecycle = InjectorLifecycle.ACTIVE
        if details:
            self.details.update(details)

    def mark_recovered(self, details: dict[str, Any] | None = None) -> None:
        """Transition injector to RECOVERED state."""
        self.lifecycle = InjectorLifecycle.RECOVERED
        self.recovered_at = datetime.now(UTC)
        if details:
            self.details.update(details)

    def mark_failed(self, error: str) -> None:
        """Transition injector to FAILED state."""
        self.lifecycle = InjectorLifecycle.FAILED
        self.details["error"] = error

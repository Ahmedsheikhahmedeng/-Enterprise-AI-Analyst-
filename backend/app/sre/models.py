"""SQLAlchemy models for SRE, SLI/SLO, Alerts, Incidents, Runbooks, and Release Gates."""

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.sre.enums import (
    AlertSeverityEnum,
    AlertStatusEnum,
    IncidentSeverityEnum,
    IncidentStatusEnum,
    MaintenanceStatusEnum,
    MetricTypeEnum,
    ReleaseGateDecisionEnum,
    SLOTypeEnum,
)


class SLIDefinition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Service Level Indicator (SLI) metric definition."""

    __tablename__ = "sli_definitions"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=MetricTypeEnum.AVAILABILITY.value,
        index=True,
    )
    query_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="ratio")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    slos: Mapped[list["SLODefinition"]] = relationship(
        "SLODefinition", back_populates="sli", cascade="all, delete-orphan"
    )


class SLODefinition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Service Level Objective (SLO) target definition."""

    __tablename__ = "slo_definitions"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    sli_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sli_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.999)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=86400)
    objective_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=SLOTypeEnum.AVAILABILITY.value,
    )
    warning_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.995)
    critical_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.990)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    sli: Mapped["SLIDefinition"] = relationship("SLIDefinition", back_populates="slos")


class Runbook(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Operational runbook containing diagnostic and safe remediation procedures."""

    __tablename__ = "runbooks"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(200), nullable=False)
    symptoms: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    diagnostic_steps: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    safe_actions: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    rollback_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str] = mapped_column(String(120), nullable=False, default="sre-team")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)


class AlertRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Alert trigger evaluation rule linked to SLI, SLO, or Runbook."""

    __tablename__ = "alert_rules"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    sli_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sli_definitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    slo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("slo_definitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    runbook_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runbooks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=AlertSeverityEnum.WARNING.value,
        index=True,
    )
    condition_operator: Mapped[str] = mapped_column(String(10), nullable=False, default=">")
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class Incident(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Enterprise operational incident tracking record."""

    __tablename__ = "incidents"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=IncidentSeverityEnum.SEV3.value,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=IncidentStatusEnum.OPEN.value,
        index=True,
    )
    incident_commander_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    primary_responder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    service_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        index=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mitigated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    postmortem_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    events: Mapped[list["IncidentEvent"]] = relationship(
        "IncidentEvent",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentEvent.created_at",
    )
    alerts: Mapped[list["Alert"]] = relationship("Alert", back_populates="incident")


class Alert(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Operational alert record with deduplication and correlation tracking."""

    __tablename__ = "alerts"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=AlertSeverityEnum.WARNING.value,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=AlertStatusEnum.FIRING.value,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="sre_engine")
    metric: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sli_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    slo_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        index=True,
    )
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        index=True,
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    incident: Mapped["Incident | None"] = relationship("Incident", back_populates="alerts")
    events: Mapped[list["AlertEvent"]] = relationship(
        "AlertEvent",
        back_populates="alert",
        cascade="all, delete-orphan",
        order_by="AlertEvent.created_at",
    )


class AlertEvent(Base, UUIDPrimaryKeyMixin):
    """Immutable audit trail of alert lifecycle changes and occurrences."""

    __tablename__ = "alert_events"

    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        index=True,
    )

    alert: Mapped["Alert"] = relationship("Alert", back_populates="events")


class IncidentEvent(Base, UUIDPrimaryKeyMixin):
    """Immutable timeline event in an incident lifecycle."""

    __tablename__ = "incident_events"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        index=True,
    )

    incident: Mapped["Incident"] = relationship("Incident", back_populates="events")


class MaintenanceWindow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Scheduled maintenance window during which certain alerts are suppressed."""

    __tablename__ = "maintenance_windows"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    service: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=MaintenanceStatusEnum.SCHEDULED.value,
        index=True,
    )


class OnCallSchedule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Abstraction for on-call roster and primary responder rotation."""

    __tablename__ = "oncall_schedules"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    schedule_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EscalationPolicy(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Escalation sequence defining tiered responders for unresolved incidents."""

    __tablename__ = "escalation_policies"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )


class AlertRoutingRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Routing rules defining which alerts map to in-app or abstract channels."""

    __tablename__ = "alert_routing_rules"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    service: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    severity: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False, default="in_app")
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class ReleaseSafetyCheck(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Audit record of automated release safety evaluations."""

    __tablename__ = "release_safety_checks"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    service: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    evaluated_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decision: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ReleaseGateDecisionEnum.ALLOW.value,
        index=True,
    )
    reasons: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    error_budget_remaining_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_incidents_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recent_error_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
        index=True,
    )

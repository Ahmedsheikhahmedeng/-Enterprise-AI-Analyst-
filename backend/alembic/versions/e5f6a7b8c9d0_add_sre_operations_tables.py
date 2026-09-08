"""add_sre_operations_tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-07 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create SRE operations tables for SLI, SLO, Alerts, Incidents, Runbooks, Maintenance, and Release Gates."""

    # 1. sli_definitions
    op.create_table(
        "sli_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column("metric_type", sa.String(length=50), nullable=False),
        sa.Column(
            "query_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("unit", sa.String(length=30), nullable=False, server_default="ratio"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sli_definitions_organization_id", "sli_definitions", ["organization_id"], unique=False
    )
    op.create_index("ix_sli_definitions_name", "sli_definitions", ["name"], unique=False)
    op.create_index("ix_sli_definitions_service", "sli_definitions", ["service"], unique=False)
    op.create_index(
        "ix_sli_definitions_metric_type", "sli_definitions", ["metric_type"], unique=False
    )
    op.create_index("ix_sli_definitions_enabled", "sli_definitions", ["enabled"], unique=False)

    # 2. slo_definitions
    op.create_table(
        "slo_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("sli_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column("target_value", sa.Float(), nullable=False, server_default="0.999"),
        sa.Column("window_seconds", sa.Integer(), nullable=False, server_default="86400"),
        sa.Column(
            "objective_type", sa.String(length=50), nullable=False, server_default="AVAILABILITY"
        ),
        sa.Column("warning_threshold", sa.Float(), nullable=False, server_default="0.995"),
        sa.Column("critical_threshold", sa.Float(), nullable=False, server_default="0.990"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sli_id"], ["sli_definitions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_slo_definitions_organization_id", "slo_definitions", ["organization_id"], unique=False
    )
    op.create_index("ix_slo_definitions_sli_id", "slo_definitions", ["sli_id"], unique=False)
    op.create_index("ix_slo_definitions_name", "slo_definitions", ["name"], unique=False)
    op.create_index("ix_slo_definitions_service", "slo_definitions", ["service"], unique=False)
    op.create_index("ix_slo_definitions_enabled", "slo_definitions", ["enabled"], unique=False)

    # 3. runbooks
    op.create_table(
        "runbooks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column("trigger", sa.String(length=200), nullable=False),
        sa.Column(
            "symptoms",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "diagnostic_steps",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "safe_actions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("rollback_notes", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=120), nullable=False, server_default="sre-team"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runbooks_organization_id", "runbooks", ["organization_id"], unique=False)
    op.create_index("ix_runbooks_name", "runbooks", ["name"], unique=False)
    op.create_index("ix_runbooks_service", "runbooks", ["service"], unique=False)
    op.create_index("ix_runbooks_is_published", "runbooks", ["is_published"], unique=False)

    # 4. alert_rules
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("sli_id", sa.UUID(), nullable=True),
        sa.Column("slo_id", sa.UUID(), nullable=True),
        sa.Column("runbook_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False, server_default="WARNING"),
        sa.Column("condition_operator", sa.String(length=10), nullable=False, server_default=">"),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sli_id"], ["sli_definitions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["slo_id"], ["slo_definitions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["runbook_id"], ["runbooks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_alert_rules_organization_id", "alert_rules", ["organization_id"], unique=False
    )
    op.create_index("ix_alert_rules_sli_id", "alert_rules", ["sli_id"], unique=False)
    op.create_index("ix_alert_rules_slo_id", "alert_rules", ["slo_id"], unique=False)
    op.create_index("ix_alert_rules_runbook_id", "alert_rules", ["runbook_id"], unique=False)
    op.create_index("ix_alert_rules_name", "alert_rules", ["name"], unique=False)
    op.create_index("ix_alert_rules_service", "alert_rules", ["service"], unique=False)
    op.create_index("ix_alert_rules_severity", "alert_rules", ["severity"], unique=False)
    op.create_index("ix_alert_rules_enabled", "alert_rules", ["enabled"], unique=False)

    # 5. incidents
    op.create_table(
        "incidents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="SEV3"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="OPEN"),
        sa.Column("incident_commander_id", sa.UUID(), nullable=True),
        sa.Column("primary_responder_id", sa.UUID(), nullable=True),
        sa.Column("service_owner", sa.String(length=120), nullable=True),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mitigated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("postmortem_url", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["incident_commander_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["primary_responder_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_organization_id", "incidents", ["organization_id"], unique=False)
    op.create_index("ix_incidents_service", "incidents", ["service"], unique=False)
    op.create_index("ix_incidents_severity", "incidents", ["severity"], unique=False)
    op.create_index("ix_incidents_status", "incidents", ["status"], unique=False)
    op.create_index("ix_incidents_opened_at", "incidents", ["opened_at"], unique=False)

    # 6. alerts
    op.create_table(
        "alerts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("rule_id", sa.UUID(), nullable=True),
        sa.Column("incident_id", sa.UUID(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False, server_default="WARNING"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="FIRING"),
        sa.Column("source", sa.String(length=100), nullable=False, server_default="sre_engine"),
        sa.Column("metric", sa.String(length=100), nullable=False),
        sa.Column("sli_name", sa.String(length=120), nullable=True),
        sa.Column("slo_name", sa.String(length=120), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column(
            "starts_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_organization_id", "alerts", ["organization_id"], unique=False)
    op.create_index("ix_alerts_rule_id", "alerts", ["rule_id"], unique=False)
    op.create_index("ix_alerts_incident_id", "alerts", ["incident_id"], unique=False)
    op.create_index("ix_alerts_fingerprint", "alerts", ["fingerprint"], unique=False)
    op.create_index("ix_alerts_name", "alerts", ["name"], unique=False)
    op.create_index("ix_alerts_service", "alerts", ["service"], unique=False)
    op.create_index("ix_alerts_severity", "alerts", ["severity"], unique=False)
    op.create_index("ix_alerts_status", "alerts", ["status"], unique=False)
    op.create_index("ix_alerts_metric", "alerts", ["metric"], unique=False)
    op.create_index("ix_alerts_starts_at", "alerts", ["starts_at"], unique=False)
    op.create_index("ix_alerts_last_seen_at", "alerts", ["last_seen_at"], unique=False)
    op.create_index("ix_alerts_trace_id", "alerts", ["trace_id"], unique=False)
    op.create_index("ix_alerts_request_id", "alerts", ["request_id"], unique=False)

    # 7. alert_events
    op.create_table(
        "alert_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("alert_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_events_alert_id", "alert_events", ["alert_id"], unique=False)
    op.create_index(
        "ix_alert_events_organization_id", "alert_events", ["organization_id"], unique=False
    )
    op.create_index("ix_alert_events_event_type", "alert_events", ["event_type"], unique=False)
    op.create_index("ix_alert_events_created_at", "alert_events", ["created_at"], unique=False)

    # 8. incident_events
    op.create_table(
        "incident_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("incident_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_incident_events_incident_id", "incident_events", ["incident_id"], unique=False
    )
    op.create_index(
        "ix_incident_events_organization_id", "incident_events", ["organization_id"], unique=False
    )
    op.create_index(
        "ix_incident_events_event_type", "incident_events", ["event_type"], unique=False
    )
    op.create_index(
        "ix_incident_events_correlation_id", "incident_events", ["correlation_id"], unique=False
    )
    op.create_index(
        "ix_incident_events_created_at", "incident_events", ["created_at"], unique=False
    )

    # 9. maintenance_windows
    op.create_table(
        "maintenance_windows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("service", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="SCHEDULED"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_maintenance_windows_organization_id",
        "maintenance_windows",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_windows_service", "maintenance_windows", ["service"], unique=False
    )
    op.create_index(
        "ix_maintenance_windows_starts_at", "maintenance_windows", ["starts_at"], unique=False
    )
    op.create_index(
        "ix_maintenance_windows_ends_at", "maintenance_windows", ["ends_at"], unique=False
    )
    op.create_index(
        "ix_maintenance_windows_status", "maintenance_windows", ["status"], unique=False
    )

    # 10. oncall_schedules
    op.create_table(
        "oncall_schedules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column(
            "schedule_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("timezone", sa.String(length=50), nullable=False, server_default="UTC"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_oncall_schedules_organization_id", "oncall_schedules", ["organization_id"], unique=False
    )
    op.create_index("ix_oncall_schedules_service", "oncall_schedules", ["service"], unique=False)

    # 11. escalation_policies
    op.create_table(
        "escalation_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "steps",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_escalation_policies_organization_id",
        "escalation_policies",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_escalation_policies_service", "escalation_policies", ["service"], unique=False
    )

    # 12. alert_routing_rules
    op.create_table(
        "alert_routing_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("service", sa.String(length=100), nullable=True),
        sa.Column("severity", sa.String(length=30), nullable=True),
        sa.Column("environment", sa.String(length=50), nullable=True),
        sa.Column("provider_type", sa.String(length=50), nullable=False, server_default="in_app"),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_alert_routing_rules_organization_id",
        "alert_routing_rules",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_alert_routing_rules_service", "alert_routing_rules", ["service"], unique=False
    )
    op.create_index(
        "ix_alert_routing_rules_severity", "alert_routing_rules", ["severity"], unique=False
    )
    op.create_index(
        "ix_alert_routing_rules_enabled", "alert_routing_rules", ["enabled"], unique=False
    )

    # 13. release_safety_checks
    op.create_table(
        "release_safety_checks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column("evaluated_by", sa.String(length=120), nullable=True),
        sa.Column("decision", sa.String(length=20), nullable=False, server_default="ALLOW"),
        sa.Column(
            "reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("error_budget_remaining_pct", sa.Float(), nullable=True),
        sa.Column("open_incidents_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recent_error_rate", sa.Float(), nullable=True),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_release_safety_checks_organization_id",
        "release_safety_checks",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_release_safety_checks_service", "release_safety_checks", ["service"], unique=False
    )
    op.create_index(
        "ix_release_safety_checks_decision", "release_safety_checks", ["decision"], unique=False
    )
    op.create_index(
        "ix_release_safety_checks_evaluated_at",
        "release_safety_checks",
        ["evaluated_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop SRE operations tables in reverse order."""
    op.drop_table("release_safety_checks")
    op.drop_table("alert_routing_rules")
    op.drop_table("escalation_policies")
    op.drop_table("oncall_schedules")
    op.drop_table("maintenance_windows")
    op.drop_table("incident_events")
    op.drop_table("alert_events")
    op.drop_table("alerts")
    op.drop_table("incidents")
    op.drop_table("alert_rules")
    op.drop_table("runbooks")
    op.drop_table("slo_definitions")
    op.drop_table("sli_definitions")

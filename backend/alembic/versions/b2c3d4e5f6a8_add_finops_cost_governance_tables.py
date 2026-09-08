"""Add enterprise finops and AI cost governance tables

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-09-07 23:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a8"
down_revision: str | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. cost_events
    op.create_table(
        "cost_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("agent_session_id", sa.String(length=64), nullable=True),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cached_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "estimated_cost",
            sa.Numeric(precision=14, scale=8),
            server_default="0.0",
            nullable=False,
        ),
        sa.Column("currency", sa.String(length=8), server_default="USD", nullable=False),
        sa.Column("pricing_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_retry", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_failed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "metadata_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cost_events_organization_id", "cost_events", ["organization_id"])
    op.create_index("ix_cost_events_user_id", "cost_events", ["user_id"])
    op.create_index("ix_cost_events_org_timestamp", "cost_events", ["organization_id", "timestamp"])
    op.create_index("ix_cost_events_provider_model", "cost_events", ["provider", "model"])
    op.create_index("ix_cost_events_operation", "cost_events", ["operation"])
    op.create_index("ix_cost_events_request_id", "cost_events", ["request_id"])
    op.create_index("ix_cost_events_pricing_ver", "cost_events", ["pricing_version"])
    op.create_index("ix_cost_events_trace_id", "cost_events", ["trace_id"])
    op.create_index("ix_cost_events_agent_session_id", "cost_events", ["agent_session_id"])
    op.create_index("ix_cost_events_job_id", "cost_events", ["job_id"])

    # 2. model_pricing
    op.create_table(
        "model_pricing",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("input_price_per_1m", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("output_price_per_1m", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("cached_input_price_per_1m", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("currency", sa.String(length=8), server_default="USD", nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "source", sa.String(length=64), server_default="CONFIGURED_ESTIMATE", nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_pricing_provider_model", "model_pricing", ["provider", "model"])
    op.create_index(
        "ix_model_pricing_version", "model_pricing", ["provider", "model", "version"], unique=True
    )
    op.create_index(
        "ix_model_pricing_effective", "model_pricing", ["effective_from", "effective_until"]
    )

    # 3. finops_budgets
    op.create_table(
        "finops_budgets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=32), server_default="ORGANIZATION", nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=True),
        sa.Column("parent_budget_id", sa.String(length=64), nullable=True),
        sa.Column("period", sa.String(length=16), server_default="MONTHLY", nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=8), server_default="USD", nullable=False),
        sa.Column("warning_percent", sa.Float(), server_default="80.0", nullable=False),
        sa.Column("critical_percent", sa.Float(), server_default="95.0", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_finops_budgets_organization_id", "finops_budgets", ["organization_id"])
    op.create_index("ix_finops_budgets_parent_budget_id", "finops_budgets", ["parent_budget_id"])
    op.create_index(
        "ix_finops_budgets_org_scope", "finops_budgets", ["organization_id", "scope", "scope_id"]
    )
    op.create_index("ix_finops_budgets_period", "finops_budgets", ["period"])

    # 4. finops_quotas
    op.create_table(
        "finops_quotas",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quota_type", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=32), server_default="ORGANIZATION", nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=True),
        sa.Column("limit_value", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("period_seconds", sa.Integer(), server_default="86400", nullable=False),
        sa.Column("enforcement_mode", sa.String(length=16), server_default="BLOCK", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_finops_quotas_organization_id", "finops_quotas", ["organization_id"])
    op.create_index("ix_finops_quotas_org_type", "finops_quotas", ["organization_id", "quota_type"])

    # 5. finops_cost_policies
    op.create_table(
        "finops_cost_policies",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("max_cost_per_request", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("max_cost_per_day", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("max_tokens_per_request", sa.Integer(), nullable=True),
        sa.Column("max_tokens_per_day", sa.Integer(), nullable=True),
        sa.Column("max_llm_calls_per_run", sa.Integer(), nullable=True),
        sa.Column("enforcement_mode", sa.String(length=16), server_default="BLOCK", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_finops_cost_policies_organization_id", "finops_cost_policies", ["organization_id"]
    )

    # 6. finops_cost_anomalies
    op.create_table(
        "finops_cost_anomalies",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("anomaly_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), server_default="WARNING", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="OPEN", nullable=False),
        sa.Column("baseline_amount", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("actual_amount", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("deviation_percent", sa.Float(), nullable=False),
        sa.Column(
            "estimated_impact",
            sa.Numeric(precision=12, scale=4),
            server_default="0.0",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("affected_entity", sa.String(length=128), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_finops_cost_anomalies_organization_id", "finops_cost_anomalies", ["organization_id"]
    )
    op.create_index(
        "ix_finops_anomalies_org_detected",
        "finops_cost_anomalies",
        ["organization_id", "detected_at"],
    )
    op.create_index("ix_finops_anomalies_status", "finops_cost_anomalies", ["status"])

    # 7. finops_cost_forecasts
    op.create_table(
        "finops_cost_forecasts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period", sa.String(length=16), server_default="MONTHLY", nullable=False),
        sa.Column("actual_to_date", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("forecasted_total", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("budget_limit", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "expected_overrun",
            sa.Numeric(precision=12, scale=4),
            server_default="0.0",
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), server_default="0.90", nullable=False),
        sa.Column(
            "forecast_method",
            sa.String(length=32),
            server_default="WEIGHTED_MOVING_AVERAGE",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_finops_cost_forecasts_organization_id", "finops_cost_forecasts", ["organization_id"]
    )
    op.create_index(
        "ix_finops_forecasts_org_period", "finops_cost_forecasts", ["organization_id", "period"]
    )

    # 8. finops_recommendations
    op.create_table(
        "finops_recommendations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="OPEN", nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("current_cost", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("expected_saving", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "quality_impact", sa.String(length=32), server_default="NEGLIGIBLE", nullable=False
        ),
        sa.Column("latency_impact", sa.String(length=32), server_default="NEUTRAL", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.85", nullable=False),
        sa.Column(
            "evidence", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_finops_recommendations_organization_id", "finops_recommendations", ["organization_id"]
    )
    op.create_index("ix_finops_recommendations_status", "finops_recommendations", ["status"])

    # 9. finops_reconciliations
    op.create_table(
        "finops_reconciliations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="MATCHED", nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("matched_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("missing_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("mismatched_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unknown_pricing_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "discrepancy_amount",
            sa.Numeric(precision=12, scale=4),
            server_default="0.0",
            nullable=False,
        ),
        sa.Column(
            "details", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_finops_reconciliations_organization_id", "finops_reconciliations", ["organization_id"]
    )
    op.create_index(
        "ix_finops_reconciliations_org_status",
        "finops_reconciliations",
        ["organization_id", "status"],
    )

    # 10. finops_cost_corrections
    op.create_table(
        "finops_cost_corrections",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_event_id", sa.String(length=64), nullable=False),
        sa.Column("adjustment_cost", sa.Numeric(precision=14, scale=8), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_finops_cost_corrections_organization_id", "finops_cost_corrections", ["organization_id"]
    )
    op.create_index(
        "ix_finops_corrections_original", "finops_cost_corrections", ["original_event_id"]
    )


def downgrade() -> None:
    op.drop_table("finops_cost_corrections")
    op.drop_table("finops_reconciliations")
    op.drop_table("finops_recommendations")
    op.drop_table("finops_cost_forecasts")
    op.drop_table("finops_cost_anomalies")
    op.drop_table("finops_cost_policies")
    op.drop_table("finops_quotas")
    op.drop_table("finops_budgets")
    op.drop_table("model_pricing")
    op.drop_table("cost_events")

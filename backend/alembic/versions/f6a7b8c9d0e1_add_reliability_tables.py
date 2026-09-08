"""Add enterprise reliability and chaos validation tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-07 22:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. reliability_scenarios
    op.create_table(
        "reliability_scenarios",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reliability_scenarios_category"),
        "reliability_scenarios",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reliability_scenarios_organization_id"),
        "reliability_scenarios",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_reliability_scenarios_org_cat",
        "reliability_scenarios",
        ["organization_id", "category"],
        unique=False,
    )

    # 2. reliability_runs
    op.create_table(
        "reliability_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scenario_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("environment", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("fault_type", sa.String(length=50), nullable=False),
        sa.Column("mttd_seconds", sa.Float(), nullable=True),
        sa.Column("mtta_seconds", sa.Float(), nullable=True),
        sa.Column("mttr_seconds", sa.Float(), nullable=True),
        sa.Column("time_to_recovery_seconds", sa.Float(), nullable=True),
        sa.Column("slo_impact_pct", sa.Float(), nullable=False),
        sa.Column("error_budget_consumed_pct", sa.Float(), nullable=False),
        sa.Column("alerts_created_count", sa.Integer(), nullable=False),
        sa.Column("incidents_created_count", sa.Integer(), nullable=False),
        sa.Column("release_gate_verdict", sa.String(length=20), nullable=True),
        sa.Column("failure_classification", sa.String(length=50), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scenario_id"], ["reliability_scenarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reliability_runs_organization_id"),
        "reliability_runs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reliability_runs_scenario_id"), "reliability_runs", ["scenario_id"], unique=False
    )
    op.create_index(
        op.f("ix_reliability_runs_status"), "reliability_runs", ["status"], unique=False
    )
    op.create_index(
        "ix_reliability_runs_org_status",
        "reliability_runs",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_reliability_runs_created_at", "reliability_runs", ["created_at"], unique=False
    )

    # 3. reliability_faults
    op.create_table(
        "reliability_faults",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("fault_type", sa.String(length=50), nullable=False),
        sa.Column("lifecycle", sa.String(length=30), nullable=False),
        sa.Column("injected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["reliability_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reliability_faults_run_id"), "reliability_faults", ["run_id"], unique=False
    )

    # 4. reliability_assertions
    op.create_table(
        "reliability_assertions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("assertion_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["reliability_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reliability_assertions_run_id"), "reliability_assertions", ["run_id"], unique=False
    )

    # 5. reliability_scorecards
    op.create_table(
        "reliability_scorecards",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detection_score", sa.Float(), nullable=False),
        sa.Column("recovery_score", sa.Float(), nullable=False),
        sa.Column("integrity_score", sa.Float(), nullable=False),
        sa.Column("degradation_score", sa.Float(), nullable=False),
        sa.Column("isolation_score", sa.Float(), nullable=False),
        sa.Column("slo_score", sa.Float(), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("total_scenarios_run", sa.Integer(), nullable=False),
        sa.Column("passed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("metrics_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reliability_scorecards_organization_id"),
        "reliability_scorecards",
        ["organization_id"],
        unique=False,
    )

    # 6. production_readiness_records
    op.create_table(
        "production_readiness_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("evaluator", sa.String(length=100), nullable=False),
        sa.Column("scorecard_id", sa.String(length=36), nullable=True),
        sa.Column("evaluation_factors", sa.JSON(), nullable=False),
        sa.Column("blockers", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_production_readiness_records_decision"),
        "production_readiness_records",
        ["decision"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_readiness_records_organization_id"),
        "production_readiness_records",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("production_readiness_records")
    op.drop_table("reliability_scorecards")
    op.drop_table("reliability_assertions")
    op.drop_table("reliability_faults")
    op.drop_table("reliability_runs")
    op.drop_table("reliability_scenarios")

"""add_continuous_evaluation_tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-07 13:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema with enterprise continuous evaluation tables."""
    # 1. benchmarks
    op.create_table(
        "benchmarks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("target", sa.String(length=50), nullable=False),
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("baseline_run_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
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
        sa.ForeignKeyConstraint(["dataset_id"], ["evaluation_datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["baseline_run_id"], ["evaluation_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "name", "version", name="uq_benchmarks_org_name_version"
        ),
    )
    op.create_index(
        op.f("ix_benchmarks_organization_id"), "benchmarks", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_benchmarks_dataset_id"), "benchmarks", ["dataset_id"], unique=False)
    op.create_index(
        "ix_benchmarks_org_status", "benchmarks", ["organization_id", "status"], unique=False
    )
    op.create_index(
        "ix_benchmarks_org_target", "benchmarks", ["organization_id", "target"], unique=False
    )

    # 2. evaluation_suites
    op.create_table(
        "evaluation_suites",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "benchmark_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
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
        sa.UniqueConstraint(
            "organization_id", "name", "version", name="uq_eval_suites_org_name_version"
        ),
    )
    op.create_index(
        op.f("ix_evaluation_suites_organization_id"),
        "evaluation_suites",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_eval_suites_org_status",
        "evaluation_suites",
        ["organization_id", "status"],
        unique=False,
    )

    # 3. quality_gates
    op.create_table(
        "quality_gates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
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
        op.f("ix_quality_gates_organization_id"), "quality_gates", ["organization_id"], unique=False
    )
    op.create_index(
        "ix_quality_gates_org_status", "quality_gates", ["organization_id", "status"], unique=False
    )

    # 4. quality_gate_results
    op.create_table(
        "quality_gate_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("gate_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column(
            "scorecard",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "violations",
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gate_id"], ["quality_gates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_quality_gate_results_organization_id"),
        "quality_gate_results",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quality_gate_results_gate_id"), "quality_gate_results", ["gate_id"], unique=False
    )
    op.create_index(
        op.f("ix_quality_gate_results_run_id"), "quality_gate_results", ["run_id"], unique=False
    )
    op.create_index(
        "ix_qg_results_org_gate_run",
        "quality_gate_results",
        ["organization_id", "gate_id", "run_id"],
        unique=False,
    )

    # 5. regressions
    op.create_table(
        "regressions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("benchmark_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("baseline_run_id", sa.UUID(), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("baseline_value", sa.Float(), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=False),
        sa.Column("drop_percentage", sa.Float(), nullable=False),
        sa.Column(
            "details",
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["benchmark_id"], ["benchmarks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["baseline_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_regressions_organization_id"), "regressions", ["organization_id"], unique=False
    )
    op.create_index(
        op.f("ix_regressions_benchmark_id"), "regressions", ["benchmark_id"], unique=False
    )
    op.create_index(op.f("ix_regressions_run_id"), "regressions", ["run_id"], unique=False)
    op.create_index(
        op.f("ix_regressions_baseline_run_id"), "regressions", ["baseline_run_id"], unique=False
    )
    op.create_index(
        "ix_regressions_org_run", "regressions", ["organization_id", "run_id"], unique=False
    )
    op.create_index(
        "ix_regressions_org_severity", "regressions", ["organization_id", "severity"], unique=False
    )

    # 6. calibration_results
    op.create_table(
        "calibration_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("ece", sa.Float(), nullable=False),
        sa.Column("brier_score", sa.Float(), nullable=False),
        sa.Column(
            "reliability_buckets",
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_calibration_results_organization_id"),
        "calibration_results",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calibration_results_run_id"), "calibration_results", ["run_id"], unique=False
    )
    op.create_index(
        "ix_calibration_results_org_run",
        "calibration_results",
        ["organization_id", "run_id"],
        unique=False,
    )

    # 7. production_evaluation_samples
    op.create_table(
        "production_evaluation_samples",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("source_execution_id", sa.String(length=100), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("sampling_strategy", sa.String(length=50), nullable=False),
        sa.Column(
            "data_sensitivity", sa.String(length=50), nullable=False, server_default="INTERNAL"
        ),
        sa.Column("redacted", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_production_evaluation_samples_organization_id"),
        "production_evaluation_samples",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_prod_eval_samples_org_strategy",
        "production_evaluation_samples",
        ["organization_id", "sampling_strategy"],
        unique=False,
    )
    op.create_index(
        "ix_prod_eval_samples_expires",
        "production_evaluation_samples",
        ["expires_at"],
        unique=False,
    )

    # 8. human_evaluations
    op.create_table(
        "human_evaluations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("sample_id", sa.UUID(), nullable=True),
        sa.Column("case_result_id", sa.UUID(), nullable=True),
        sa.Column("evaluator_id", sa.UUID(), nullable=False),
        sa.Column("accuracy_score", sa.Float(), nullable=False),
        sa.Column("helpfulness_score", sa.Float(), nullable=False),
        sa.Column("grounding_score", sa.Float(), nullable=False),
        sa.Column("clarity_score", sa.Float(), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["sample_id"], ["production_evaluation_samples.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["case_result_id"], ["evaluation_case_results.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["evaluator_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_human_evaluations_organization_id"),
        "human_evaluations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_human_evaluations_sample_id"), "human_evaluations", ["sample_id"], unique=False
    )
    op.create_index(
        op.f("ix_human_evaluations_case_result_id"),
        "human_evaluations",
        ["case_result_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_human_evaluations_evaluator_id"),
        "human_evaluations",
        ["evaluator_id"],
        unique=False,
    )
    op.create_index(
        "ix_human_eval_org_evaluator",
        "human_evaluations",
        ["organization_id", "evaluator_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade database schema removing continuous evaluation tables."""
    op.drop_index("ix_human_eval_org_evaluator", table_name="human_evaluations")
    op.drop_index(op.f("ix_human_evaluations_evaluator_id"), table_name="human_evaluations")
    op.drop_index(op.f("ix_human_evaluations_case_result_id"), table_name="human_evaluations")
    op.drop_index(op.f("ix_human_evaluations_sample_id"), table_name="human_evaluations")
    op.drop_index(op.f("ix_human_evaluations_organization_id"), table_name="human_evaluations")
    op.drop_table("human_evaluations")

    op.drop_index("ix_prod_eval_samples_expires", table_name="production_evaluation_samples")
    op.drop_index("ix_prod_eval_samples_org_strategy", table_name="production_evaluation_samples")
    op.drop_index(
        op.f("ix_production_evaluation_samples_organization_id"),
        table_name="production_evaluation_samples",
    )
    op.drop_table("production_evaluation_samples")

    op.drop_index("ix_calibration_results_org_run", table_name="calibration_results")
    op.drop_index(op.f("ix_calibration_results_run_id"), table_name="calibration_results")
    op.drop_index(op.f("ix_calibration_results_organization_id"), table_name="calibration_results")
    op.drop_table("calibration_results")

    op.drop_index("ix_regressions_org_severity", table_name="regressions")
    op.drop_index("ix_regressions_org_run", table_name="regressions")
    op.drop_index(op.f("ix_regressions_baseline_run_id"), table_name="regressions")
    op.drop_index(op.f("ix_regressions_run_id"), table_name="regressions")
    op.drop_index(op.f("ix_regressions_benchmark_id"), table_name="regressions")
    op.drop_index(op.f("ix_regressions_organization_id"), table_name="regressions")
    op.drop_table("regressions")

    op.drop_index("ix_qg_results_org_gate_run", table_name="quality_gate_results")
    op.drop_index(op.f("ix_quality_gate_results_run_id"), table_name="quality_gate_results")
    op.drop_index(op.f("ix_quality_gate_results_gate_id"), table_name="quality_gate_results")
    op.drop_index(
        op.f("ix_quality_gate_results_organization_id"), table_name="quality_gate_results"
    )
    op.drop_table("quality_gate_results")

    op.drop_index("ix_quality_gates_org_status", table_name="quality_gates")
    op.drop_index(op.f("ix_quality_gates_organization_id"), table_name="quality_gates")
    op.drop_table("quality_gates")

    op.drop_index("ix_eval_suites_org_status", table_name="evaluation_suites")
    op.drop_index(op.f("ix_evaluation_suites_organization_id"), table_name="evaluation_suites")
    op.drop_table("evaluation_suites")

    op.drop_index("ix_benchmarks_org_target", table_name="benchmarks")
    op.drop_index("ix_benchmarks_org_status", table_name="benchmarks")
    op.drop_index(op.f("ix_benchmarks_dataset_id"), table_name="benchmarks")
    op.drop_index(op.f("ix_benchmarks_organization_id"), table_name="benchmarks")
    op.drop_table("benchmarks")

"""add_orchestration_tables

Revision ID: a1b2c3d4e5f6
Revises: 9c0a1b2c3d4e
Create Date: 2026-09-07 12:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "9c0a1b2c3d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema with orchestration execution and step tables."""
    # 1. Create orchestration_executions table
    op.create_table(
        "orchestration_executions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=30), server_default="AUTO", nullable=False),
        sa.Column(
            "execution_strategy", sa.String(length=30), server_default="NONE", nullable=False
        ),
        sa.Column("status", sa.String(length=50), server_default="RECEIVED", nullable=False),
        sa.Column("decision", sa.String(length=50), server_default="ANSWER", nullable=False),
        sa.Column(
            "confidence_score",
            sa.Numeric(precision=5, scale=4),
            server_default=sa.text("0.0"),
            nullable=False,
        ),
        sa.Column(
            "evidence_coverage",
            sa.Numeric(precision=5, scale=4),
            server_default=sa.text("0.0"),
            nullable=False,
        ),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("clarification_prompt", sa.Text(), nullable=True),
        sa.Column(
            "citations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "conflicts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "diagnostics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_orchestration_exec_conversation"),
        "orchestration_executions",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_orchestration_exec_org_created_at"),
        "orchestration_executions",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_orchestration_exec_org_status"),
        "orchestration_executions",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_orchestration_executions_organization_id"),
        "orchestration_executions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_orchestration_executions_status"),
        "orchestration_executions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_orchestration_executions_user_id"),
        "orchestration_executions",
        ["user_id"],
        unique=False,
    )

    # 2. Create orchestration_steps table
    op.create_table(
        "orchestration_steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("execution_id", sa.UUID(), nullable=False),
        sa.Column("step_type", sa.String(length=50), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["execution_id"], ["orchestration_executions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_id", "step_order", name="uq_orchestration_steps_order"),
    )
    op.create_index(
        op.f("ix_orchestration_steps_exec_order"),
        "orchestration_steps",
        ["execution_id", "step_order"],
        unique=False,
    )
    op.create_index(
        op.f("ix_orchestration_steps_execution_id"),
        "orchestration_steps",
        ["execution_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade database schema removing orchestration tables."""
    op.drop_index(op.f("ix_orchestration_steps_execution_id"), table_name="orchestration_steps")
    op.drop_index(op.f("ix_orchestration_steps_exec_order"), table_name="orchestration_steps")
    op.drop_table("orchestration_steps")

    op.drop_index(
        op.f("ix_orchestration_executions_user_id"), table_name="orchestration_executions"
    )
    op.drop_index(op.f("ix_orchestration_executions_status"), table_name="orchestration_executions")
    op.drop_index(
        op.f("ix_orchestration_executions_organization_id"), table_name="orchestration_executions"
    )
    op.drop_index(op.f("ix_orchestration_exec_org_status"), table_name="orchestration_executions")
    op.drop_index(
        op.f("ix_orchestration_exec_org_created_at"), table_name="orchestration_executions"
    )
    op.drop_index(op.f("ix_orchestration_exec_conversation"), table_name="orchestration_executions")
    op.drop_table("orchestration_executions")

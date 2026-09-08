"""add_execution_events_table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-07 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema with execution_events table for streaming execution ledger."""
    op.create_table(
        "execution_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("execution_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["execution_id"],
            ["orchestration_executions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_id", "sequence", name="uq_execution_events_sequence"),
    )

    op.create_index(
        "ix_execution_events_exec_seq",
        "execution_events",
        ["execution_id", "sequence"],
        unique=False,
    )
    op.create_index(
        "ix_execution_events_org_created",
        "execution_events",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_execution_events_type",
        "execution_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_execution_events_execution_id",
        "execution_events",
        ["execution_id"],
        unique=False,
    )
    op.create_index(
        "ix_execution_events_organization_id",
        "execution_events",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade database schema by dropping execution_events table."""
    op.drop_index("ix_execution_events_organization_id", table_name="execution_events")
    op.drop_index("ix_execution_events_execution_id", table_name="execution_events")
    op.drop_index("ix_execution_events_type", table_name="execution_events")
    op.drop_index("ix_execution_events_org_created", table_name="execution_events")
    op.drop_index("ix_execution_events_exec_seq", table_name="execution_events")
    op.drop_table("execution_events")

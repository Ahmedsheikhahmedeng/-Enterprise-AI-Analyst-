"""add_data_source_sync_tables

Revision ID: b3a3a6feca9a
Revises: a82e5619d023
Create Date: 2026-09-06 23:05:04.551390

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3a3a6feca9a"
down_revision: str | Sequence[str] | None = "a82e5619d023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create data_source_sync_runs table
    op.create_table(
        "data_source_sync_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("data_source_id", sa.UUID(), nullable=False),
        sa.Column("sync_type", sa.String(length=50), nullable=False, server_default="full"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_synced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "meta_info",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_data_source_sync_runs_data_source_id"),
        "data_source_sync_runs",
        ["data_source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_data_source_sync_runs_organization_id"),
        "data_source_sync_runs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_ds_sync_runs_org_ds",
        "data_source_sync_runs",
        ["organization_id", "data_source_id"],
        unique=False,
    )
    op.create_index(
        "ix_ds_sync_runs_org_status",
        "data_source_sync_runs",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_ds_sync_runs_created_at",
        "data_source_sync_runs",
        ["created_at"],
        unique=False,
    )

    # 2. Add individual column indexes to align with models
    op.create_index(
        op.f("ix_memory_items_content_hash"),
        "memory_items",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_items_expires_at"),
        "memory_items",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_items_memory_type"),
        "memory_items",
        ["memory_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_items_organization_id"),
        "memory_items",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_items_status"),
        "memory_items",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_versions_memory_id"),
        "memory_versions",
        ["memory_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_memory_versions_organization_id"),
        "memory_versions",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_memory_versions_organization_id"), table_name="memory_versions")
    op.drop_index(op.f("ix_memory_versions_memory_id"), table_name="memory_versions")
    op.drop_index(op.f("ix_memory_items_status"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_organization_id"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_memory_type"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_expires_at"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_content_hash"), table_name="memory_items")

    op.drop_index("ix_ds_sync_runs_created_at", table_name="data_source_sync_runs")
    op.drop_index("ix_ds_sync_runs_org_status", table_name="data_source_sync_runs")
    op.drop_index("ix_ds_sync_runs_org_ds", table_name="data_source_sync_runs")
    op.drop_index(
        op.f("ix_data_source_sync_runs_organization_id"), table_name="data_source_sync_runs"
    )
    op.drop_index(
        op.f("ix_data_source_sync_runs_data_source_id"), table_name="data_source_sync_runs"
    )
    op.drop_table("data_source_sync_runs")

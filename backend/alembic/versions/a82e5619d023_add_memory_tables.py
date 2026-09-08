"""add_memory_tables

Revision ID: a82e5619d023
Revises: fb758e565435
Create Date: 2026-09-06 22:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a82e5619d023"
down_revision: str | Sequence[str] | None = "fb758e565435"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to add memory_items and memory_versions tables."""
    op.create_table(
        "memory_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("memory_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "source_type", sa.String(length=50), nullable=False, server_default="user_declared"
        ),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column(
            "source_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
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
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "visibility", sa.String(length=50), nullable=False, server_default="organization"
        ),
        sa.Column("privacy_level", sa.String(length=50), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        sa.Column("supersedes_memory_id", sa.UUID(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.UUID(), nullable=True),
        sa.Column(
            "meta_info",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supersedes_memory_id"], ["memory_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_items_org_status", "memory_items", ["organization_id", "status"], unique=False
    )
    op.create_index(
        "ix_memory_items_org_type", "memory_items", ["organization_id", "memory_type"], unique=False
    )
    op.create_index(
        "ix_memory_items_org_user", "memory_items", ["organization_id", "user_id"], unique=False
    )
    op.create_index(
        "ix_memory_items_org_session",
        "memory_items",
        ["organization_id", "session_id"],
        unique=False,
    )
    op.create_index(
        "ix_memory_items_org_hash",
        "memory_items",
        ["organization_id", "content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_memory_items_org_expires",
        "memory_items",
        ["organization_id", "expires_at"],
        unique=False,
    )

    op.create_table(
        "memory_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("memory_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_versions_memory_version",
        "memory_versions",
        ["memory_id", "version"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_memory_versions_memory_version", table_name="memory_versions")
    op.drop_table("memory_versions")

    op.drop_index("ix_memory_items_org_expires", table_name="memory_items")
    op.drop_index("ix_memory_items_org_hash", table_name="memory_items")
    op.drop_index("ix_memory_items_org_session", table_name="memory_items")
    op.drop_index("ix_memory_items_org_user", table_name="memory_items")
    op.drop_index("ix_memory_items_org_type", table_name="memory_items")
    op.drop_index("ix_memory_items_org_status", table_name="memory_items")
    op.drop_table("memory_items")

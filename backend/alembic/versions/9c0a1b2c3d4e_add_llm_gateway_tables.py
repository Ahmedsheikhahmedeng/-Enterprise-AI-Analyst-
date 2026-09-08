"""add_llm_gateway_tables

Revision ID: 9c0a1b2c3d4e
Revises: 8b9f0c1d2e3f
Create Date: 2026-09-07 12:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c0a1b2c3d4e"
down_revision: str | Sequence[str] | None = "8b9f0c1d2e3f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema with LLM gateway models and usage columns."""
    # 1. Add columns to llm_requests
    op.add_column("llm_requests", sa.Column("task_type", sa.String(length=50), nullable=True))
    op.add_column(
        "llm_requests",
        sa.Column("fallback_used", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "llm_requests",
        sa.Column("cache_hit", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(op.f("ix_llm_requests_task_type"), "llm_requests", ["task_type"], unique=False)

    # 2. Create tenant_llm_policies table
    op.create_table(
        "tenant_llm_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("allowed_providers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("allowed_models", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("max_tokens_per_request", sa.Integer(), nullable=True),
        sa.Column("max_cost_per_request", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("allowed_capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_residency", sa.String(length=50), server_default="ANY", nullable=False),
        sa.Column(
            "streaming_allowed", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("caching_allowed", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_tenant_llm_policies_org"),
    )
    op.create_index(
        "ix_tenant_llm_policies_organization_id",
        "tenant_llm_policies",
        ["organization_id"],
        unique=False,
    )

    # 3. Create llm_model_definitions table
    op.create_table(
        "llm_model_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=50), server_default="latest", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="ACTIVE", nullable=False),
        sa.Column("is_approved", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "input_price_per_1k",
            sa.Numeric(precision=10, scale=6),
            server_default="0.0",
            nullable=False,
        ),
        sa.Column(
            "output_price_per_1k",
            sa.Numeric(precision=10, scale=6),
            server_default="0.0",
            nullable=False,
        ),
        sa.Column("context_window", sa.Integer(), server_default="128000", nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), server_default="4096", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "model_name", "model_version", name="uq_model_def_provider_name_ver"
        ),
    )
    op.create_index(
        "ix_model_def_provider_name",
        "llm_model_definitions",
        ["provider", "model_name"],
        unique=False,
    )
    op.create_index(
        "ix_model_def_status_approved",
        "llm_model_definitions",
        ["status", "is_approved"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_model_def_status_approved", table_name="llm_model_definitions")
    op.drop_index("ix_model_def_provider_name", table_name="llm_model_definitions")
    op.drop_table("llm_model_definitions")

    op.drop_index(
        "ix_tenant_llm_policies_organization_id", table_name="tenant_llm_policies", if_exists=True
    )
    op.drop_index("ix_tenant_llm_policies_org", table_name="tenant_llm_policies", if_exists=True)
    op.drop_table("tenant_llm_policies")

    op.drop_index(op.f("ix_llm_requests_task_type"), table_name="llm_requests")
    op.drop_column("llm_requests", "cache_hit")
    op.drop_column("llm_requests", "fallback_used")
    op.drop_column("llm_requests", "task_type")

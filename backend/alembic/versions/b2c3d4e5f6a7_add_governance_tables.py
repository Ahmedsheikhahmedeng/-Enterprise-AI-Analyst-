"""add_governance_tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-07 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema with enterprise governance and approval tables."""
    # 0. Rename legacy agent approval_requests table to agent_approval_requests
    op.rename_table("approval_requests", "agent_approval_requests")
    op.execute(
        "ALTER INDEX ix_approval_requests_organization_id RENAME TO ix_agent_approval_requests_organization_id"
    )
    op.execute(
        "ALTER INDEX ix_approval_requests_session_status RENAME TO ix_agent_approval_requests_session_status"
    )

    # 1. governance_policies
    op.create_table(
        "governance_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "policy_version", name="uq_gov_policy_org_version"),
    )
    op.create_index(
        op.f("ix_governance_policies_organization_id"),
        "governance_policies",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_governance_policies_org_status",
        "governance_policies",
        ["organization_id", "status"],
        unique=False,
    )

    # 2. approval_requests
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("request_type", sa.String(length=50), nullable=False),
        sa.Column("requester_id", sa.UUID(), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("risk_level", sa.String(length=50), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("action_hash", sa.String(length=64), nullable=True),
        sa.Column("resource_hash", sa.String(length=64), nullable=True),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_approval_requests_organization_id"),
        "approval_requests",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_requests_request_type"),
        "approval_requests",
        ["request_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_requests_requester_id"),
        "approval_requests",
        ["requester_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_requests_risk_level"),
        "approval_requests",
        ["risk_level"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_requests_status"),
        "approval_requests",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_requests_expires_at"),
        "approval_requests",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_org_status",
        "approval_requests",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_org_risk",
        "approval_requests",
        ["organization_id", "risk_level"],
        unique=False,
    )
    op.create_index(
        "ix_approval_requests_org_type",
        "approval_requests",
        ["organization_id", "request_type"],
        unique=False,
    )

    # 3. approval_votes
    op.create_table(
        "approval_votes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("approval_request_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["approval_request_id"], ["approval_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "approval_request_id", "reviewer_id", name="uq_approval_votes_req_reviewer"
        ),
    )
    op.create_index(
        op.f("ix_approval_votes_organization_id"),
        "approval_votes",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_votes_approval_request_id"),
        "approval_votes",
        ["approval_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_votes_reviewer_id"),
        "approval_votes",
        ["reviewer_id"],
        unique=False,
    )

    # 4. approval_decisions
    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.String(length=50), nullable=False),
        sa.Column(
            "reviewer_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("decision_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["request_id"], ["approval_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_approval_decisions_organization_id"),
        "approval_decisions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_decisions_request_id"),
        "approval_decisions",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "ix_approval_decisions_org_request",
        "approval_decisions",
        ["organization_id", "request_id"],
        unique=False,
    )

    # 5. approval_comments
    op.create_table(
        "approval_comments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("approval_request_id", sa.UUID(), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["approval_request_id"], ["approval_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_approval_comments_organization_id"),
        "approval_comments",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_comments_approval_request_id"),
        "approval_comments",
        ["approval_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approval_comments_author_id"),
        "approval_comments",
        ["author_id"],
        unique=False,
    )
    op.create_index(
        "ix_approval_comments_request",
        "approval_comments",
        ["approval_request_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade database schema removing governance tables."""
    op.drop_index("ix_approval_comments_request", table_name="approval_comments")
    op.drop_index(op.f("ix_approval_comments_author_id"), table_name="approval_comments")
    op.drop_index(op.f("ix_approval_comments_approval_request_id"), table_name="approval_comments")
    op.drop_index(op.f("ix_approval_comments_organization_id"), table_name="approval_comments")
    op.drop_table("approval_comments")

    op.drop_index("ix_approval_decisions_org_request", table_name="approval_decisions")
    op.drop_index(op.f("ix_approval_decisions_request_id"), table_name="approval_decisions")
    op.drop_index(op.f("ix_approval_decisions_organization_id"), table_name="approval_decisions")
    op.drop_table("approval_decisions")

    op.drop_index(op.f("ix_approval_votes_reviewer_id"), table_name="approval_votes")
    op.drop_index(op.f("ix_approval_votes_approval_request_id"), table_name="approval_votes")
    op.drop_index(op.f("ix_approval_votes_organization_id"), table_name="approval_votes")
    op.drop_table("approval_votes")

    op.drop_index("ix_approval_requests_org_type", table_name="approval_requests")
    op.drop_index("ix_approval_requests_org_risk", table_name="approval_requests")
    op.drop_index("ix_approval_requests_org_status", table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_expires_at"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_status"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_risk_level"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_requester_id"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_request_type"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_organization_id"), table_name="approval_requests")
    op.drop_table("approval_requests")

    op.drop_index("ix_governance_policies_org_status", table_name="governance_policies")
    op.drop_index(op.f("ix_governance_policies_organization_id"), table_name="governance_policies")
    op.drop_table("governance_policies")

    # Restore legacy agent approval_requests table
    op.rename_table("agent_approval_requests", "approval_requests")
    op.execute(
        "ALTER INDEX ix_agent_approval_requests_organization_id RENAME TO ix_approval_requests_organization_id"
    )
    op.execute(
        "ALTER INDEX ix_agent_approval_requests_session_status RENAME TO ix_approval_requests_session_status"
    )

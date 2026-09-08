"""Add enterprise compliance and security governance tables

Revision ID: a1b2c3d4e5f7
Revises: f6a7b8c9d0e1
Create Date: 2026-09-07 23:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. compliance_controls
    op.create_table(
        "compliance_controls",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("framework", sa.String(length=64), nullable=False),
        sa.Column("control_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="HIGH", nullable=False),
        sa.Column("automated", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSON(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_controls_framework", "compliance_controls", ["framework"])
    op.create_index("ix_compliance_controls_control_code", "compliance_controls", ["control_code"])
    op.create_index("ix_compliance_controls_category", "compliance_controls", ["category"])
    op.create_index("ix_compliance_controls_severity", "compliance_controls", ["severity"])
    op.create_index(
        "ix_compliance_controls_organization_id", "compliance_controls", ["organization_id"]
    )
    op.create_index(
        "ix_compliance_controls_framework_code",
        "compliance_controls",
        ["framework", "control_code"],
    )
    op.create_index(
        "ix_compliance_controls_org_enabled", "compliance_controls", ["organization_id", "enabled"]
    )

    # 2. control_assessments
    op.create_table(
        "control_assessments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("control_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "assessor_type",
            sa.String(length=64),
            server_default="AUTOMATED_ASSESSOR",
            nullable=False,
        ),
        sa.Column("evidence_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "details", postgresql.JSON(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.ForeignKeyConstraint(["control_id"], ["compliance_controls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_control_assessments_control_id", "control_assessments", ["control_id"])
    op.create_index(
        "ix_control_assessments_organization_id", "control_assessments", ["organization_id"]
    )
    op.create_index("ix_control_assessments_status", "control_assessments", ["status"])
    op.create_index("ix_control_assessments_assessed_at", "control_assessments", ["assessed_at"])
    op.create_index(
        "ix_control_assessments_org_status", "control_assessments", ["organization_id", "status"]
    )

    # 3. compliance_evidence
    op.create_table(
        "compliance_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("control_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_payload",
            postgresql.JSON(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("source_record_id", sa.String(length=120), nullable=True),
        sa.Column("actor", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["control_id"], ["compliance_controls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_evidence_control_id", "compliance_evidence", ["control_id"])
    op.create_index(
        "ix_compliance_evidence_organization_id", "compliance_evidence", ["organization_id"]
    )
    op.create_index(
        "ix_compliance_evidence_evidence_type", "compliance_evidence", ["evidence_type"]
    )
    op.create_index("ix_compliance_evidence_hash", "compliance_evidence", ["hash"])
    op.create_index("ix_compliance_evidence_captured_at", "compliance_evidence", ["captured_at"])
    op.create_index("ix_compliance_evidence_expires_at", "compliance_evidence", ["expires_at"])
    op.create_index(
        "ix_compliance_evidence_org_control",
        "compliance_evidence",
        ["organization_id", "control_id"],
    )
    op.create_index(
        "ix_compliance_evidence_freshness", "compliance_evidence", ["captured_at", "expires_at"]
    )

    # 4. data_classifications
    op.create_table(
        "data_classifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=False),
        sa.Column("classification", sa.String(length=30), nullable=False),
        sa.Column(
            "pii_types_detected",
            postgresql.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("classified_by", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_data_classifications_organization_id", "data_classifications", ["organization_id"]
    )
    op.create_index(
        "ix_data_classifications_resource_type", "data_classifications", ["resource_type"]
    )
    op.create_index("ix_data_classifications_resource_id", "data_classifications", ["resource_id"])
    op.create_index(
        "ix_data_classifications_classification", "data_classifications", ["classification"]
    )
    op.create_index(
        "ix_data_classifications_org_res",
        "data_classifications",
        ["organization_id", "resource_type", "resource_id"],
        unique=True,
    )

    # 5. data_handling_policies
    op.create_table(
        "data_handling_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("classification", sa.String(length=30), nullable=False),
        sa.Column(
            "allowed_models",
            postgresql.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "allowed_providers",
            postgresql.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "allow_external_processing",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("allow_export", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "allow_agent_usage", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("allow_embedding", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("retention_days", sa.Integer(), server_default="365", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_data_handling_policies_organization_id", "data_handling_policies", ["organization_id"]
    )
    op.create_index(
        "ix_data_handling_policies_classification", "data_handling_policies", ["classification"]
    )
    op.create_index(
        "ix_data_handling_policies_org_class",
        "data_handling_policies",
        ["organization_id", "classification"],
        unique=True,
    )

    # 6. pii_handling_policies
    op.create_table(
        "pii_handling_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pii_category", sa.String(length=40), nullable=False),
        sa.Column("action", sa.String(length=30), server_default="MASK", nullable=False),
        sa.Column(
            "mask_pattern",
            sa.String(length=120),
            server_default="[REDACTED_{category}]",
            nullable=False,
        ),
        sa.Column("block_export", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "audit_on_detection", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pii_handling_policies_organization_id", "pii_handling_policies", ["organization_id"]
    )
    op.create_index(
        "ix_pii_handling_policies_pii_category", "pii_handling_policies", ["pii_category"]
    )
    op.create_index(
        "ix_pii_handling_policies_org_cat",
        "pii_handling_policies",
        ["organization_id", "pii_category"],
        unique=True,
    )

    # 7. retention_policies
    op.create_table(
        "retention_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("retention_days", sa.Integer(), server_default="90", nullable=False),
        sa.Column(
            "legal_hold_exempt", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("delete_after", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_retention_policies_organization_id", "retention_policies", ["organization_id"]
    )
    op.create_index("ix_retention_policies_resource_type", "retention_policies", ["resource_type"])
    op.create_index(
        "ix_retention_policies_org_res",
        "retention_policies",
        ["organization_id", "resource_type"],
        unique=True,
    )

    # 8. legal_holds
    op.create_table(
        "legal_holds",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resources", postgresql.JSON(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_legal_holds_organization_id", "legal_holds", ["organization_id"])
    op.create_index("ix_legal_holds_active", "legal_holds", ["active"])
    op.create_index("ix_legal_holds_ends_at", "legal_holds", ["ends_at"])
    op.create_index("ix_legal_holds_org_active", "legal_holds", ["organization_id", "active"])

    # 9. access_reviews
    op.create_table(
        "access_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("initiated_by", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="PENDING", nullable=False),
        sa.Column("total_users_reviewed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("flagged_inactive_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_access_reviews_organization_id", "access_reviews", ["organization_id"])
    op.create_index("ix_access_reviews_status", "access_reviews", ["status"])

    # 10. access_review_items
    op.create_table(
        "access_review_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_email", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column(
            "permissions",
            postgresql.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_status", sa.String(length=30), server_default="PENDING", nullable=False),
        sa.Column("recommendation", sa.String(length=64), nullable=True),
        sa.Column("reviewed_by", sa.String(length=120), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["review_id"], ["access_reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_access_review_items_review_id", "access_review_items", ["review_id"])
    op.create_index(
        "ix_access_review_items_organization_id", "access_review_items", ["organization_id"]
    )
    op.create_index("ix_access_review_items_user_id", "access_review_items", ["user_id"])
    op.create_index(
        "ix_access_review_items_review_status", "access_review_items", ["review_status"]
    )
    op.create_index(
        "ix_access_review_items_org_status",
        "access_review_items",
        ["organization_id", "review_status"],
    )

    # 11. security_findings
    op.create_table(
        "security_findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("control_id", sa.String(length=64), nullable=True),
        sa.Column("severity", sa.String(length=20), server_default="MEDIUM", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="OPEN", nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "source", sa.String(length=64), server_default="AUTOMATED_SCANNER", nullable=False
        ),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner", sa.String(length=120), nullable=True),
        sa.Column(
            "details", postgresql.JSON(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.ForeignKeyConstraint(["control_id"], ["compliance_controls.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_security_findings_organization_id", "security_findings", ["organization_id"]
    )
    op.create_index("ix_security_findings_control_id", "security_findings", ["control_id"])
    op.create_index("ix_security_findings_severity", "security_findings", ["severity"])
    op.create_index("ix_security_findings_status", "security_findings", ["status"])
    op.create_index(
        "ix_security_findings_org_severity_status",
        "security_findings",
        ["organization_id", "severity", "status"],
    )

    # 12. risk_acceptances
    op.create_table(
        "risk_acceptances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finding_id", sa.String(length=36), nullable=False),
        sa.Column("accepted_by", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("privileged_approval_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["finding_id"], ["security_findings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_acceptances_organization_id", "risk_acceptances", ["organization_id"])
    op.create_index("ix_risk_acceptances_finding_id", "risk_acceptances", ["finding_id"])
    op.create_index("ix_risk_acceptances_expires_at", "risk_acceptances", ["expires_at"])
    op.create_index(
        "ix_risk_acceptances_org_exp", "risk_acceptances", ["organization_id", "expires_at"]
    )

    # 13. privacy_requests
    op.create_table(
        "privacy_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="REQUESTED", nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=False),
        sa.Column(
            "resources", postgresql.JSON(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column("governance_approval_id", sa.String(length=120), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_privacy_requests_organization_id", "privacy_requests", ["organization_id"])
    op.create_index("ix_privacy_requests_user_id", "privacy_requests", ["user_id"])
    op.create_index("ix_privacy_requests_request_type", "privacy_requests", ["request_type"])
    op.create_index("ix_privacy_requests_status", "privacy_requests", ["status"])
    op.create_index(
        "ix_privacy_requests_org_status", "privacy_requests", ["organization_id", "status"]
    )


def downgrade() -> None:
    op.drop_table("privacy_requests")
    op.drop_table("risk_acceptances")
    op.drop_table("security_findings")
    op.drop_table("access_review_items")
    op.drop_table("access_reviews")
    op.drop_table("legal_holds")
    op.drop_table("retention_policies")
    op.drop_table("pii_handling_policies")
    op.drop_table("data_handling_policies")
    op.drop_table("data_classifications")
    op.drop_table("compliance_evidence")
    op.drop_table("control_assessments")
    op.drop_table("compliance_controls")

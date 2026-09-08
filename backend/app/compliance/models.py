"""SQLAlchemy models for Enterprise Security & Compliance Governance."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ComplianceControl(Base):
    """Catalog of security and compliance controls."""

    __tablename__ = "compliance_controls"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    framework: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    control_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="HIGH", index=True)
    automated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    assessments: Mapped[list["ControlAssessment"]] = relationship(
        "ControlAssessment", back_populates="control", cascade="all, delete-orphan"
    )
    evidence_items: Mapped[list["ComplianceEvidence"]] = relationship(
        "ComplianceEvidence", back_populates="control", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_compliance_controls_framework_code", "framework", "control_code"),
        Index("ix_compliance_controls_org_enabled", "organization_id", "enabled"),
    )


class ControlAssessment(Base):
    """Historical and continuous evaluation result for a compliance control."""

    __tablename__ = "control_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    control_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("compliance_controls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    assessor_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="AUTOMATED_ASSESSOR"
    )
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    control: Mapped["ComplianceControl"] = relationship(
        "ComplianceControl", back_populates="assessments"
    )

    __table_args__ = (Index("ix_control_assessments_org_status", "organization_id", "status"),)


class ComplianceEvidence(Base):
    """Immutable, versioned verification evidence supporting control assertions."""

    __tablename__ = "compliance_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    control_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("compliance_controls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)

    control: Mapped["ComplianceControl"] = relationship(
        "ComplianceControl", back_populates="evidence_items"
    )

    __table_args__ = (
        Index("ix_compliance_evidence_org_control", "organization_id", "control_id"),
        Index("ix_compliance_evidence_freshness", "captured_at", "expires_at"),
    )


class DataClassificationRecord(Base):
    """Classification catalog associating datasets, documents, or tables with a sensitivity tier."""

    __tablename__ = "data_classifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    classification: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    pii_types_detected: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    classified_by: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_data_classifications_org_res",
            "organization_id",
            "resource_type",
            "resource_id",
            unique=True,
        ),
    )


class DataHandlingPolicy(Base):
    """Tenant-scoped policy governing acceptable models, providers, and exports per sensitivity tier."""

    __tablename__ = "data_handling_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    classification: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    allowed_models: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allowed_providers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    allow_external_processing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_export: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_agent_usage: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_embedding: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=365, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_data_handling_policies_org_class", "organization_id", "classification", unique=True
        ),
    )


class PIIHandlingPolicy(Base):
    """Policy directing detection, masking, blocking, and auditing for PII categories."""

    __tablename__ = "pii_handling_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    pii_category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False, default="MASK")
    mask_pattern: Mapped[str] = mapped_column(
        String(120), default="[REDACTED_{category}]", nullable=False
    )
    block_export: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    audit_on_detection: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_pii_handling_policies_org_cat", "organization_id", "pii_category", unique=True),
    )


class RetentionPolicy(Base):
    """Data retention durations and eligibility criteria per resource domain."""

    __tablename__ = "retention_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    legal_hold_exempt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    delete_after: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_retention_policies_org_res", "organization_id", "resource_type", unique=True),
    )


class LegalHold(Base):
    """Legal hold freezing deletion eligibility for specified resources or tenants."""

    __tablename__ = "legal_holds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    resources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (Index("ix_legal_holds_org_active", "organization_id", "active"),)


class AccessReview(Base):
    """Periodic campaign evaluating user permissions, stale roles, and inactive accounts."""

    __tablename__ = "access_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    initiated_by: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    total_users_reviewed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    flagged_inactive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["AccessReviewItem"]] = relationship(
        "AccessReviewItem", back_populates="review", cascade="all, delete-orphan"
    )


class AccessReviewItem(Base):
    """Individual user evaluation line item within an access review campaign."""

    __tablename__ = "access_review_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("access_reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    user_email: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    review_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="PENDING", index=True
    )
    recommendation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    review: Mapped["AccessReview"] = relationship("AccessReview", back_populates="items")

    __table_args__ = (
        Index("ix_access_review_items_org_status", "organization_id", "review_status"),
    )


class SecurityFinding(Base):
    """Identified vulnerability or compliance finding with aging and remediation tracking."""

    __tablename__ = "security_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    control_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("compliance_controls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM", index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="AUTOMATED_SCANNER")
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    risk_acceptances: Mapped[list["RiskAcceptance"]] = relationship(
        "RiskAcceptance", back_populates="finding", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_security_findings_org_severity_status", "organization_id", "severity", "status"),
    )


class RiskAcceptance(Base):
    """Formal, privileged acceptance of a security finding with expiration and audit justification."""

    __tablename__ = "risk_acceptances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    finding_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("security_findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    accepted_by: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    privileged_approval_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    finding: Mapped["SecurityFinding"] = relationship(
        "SecurityFinding", back_populates="risk_acceptances"
    )

    __table_args__ = (Index("ix_risk_acceptances_org_exp", "organization_id", "expires_at"),)


class PrivacyRequest(Base):
    """Data subject privacy action (Right-to-Delete, Export, etc.) following governed review."""

    __tablename__ = "privacy_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="REQUESTED", index=True)
    requested_by: Mapped[str] = mapped_column(String(120), nullable=False)
    resources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    governance_approval_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (Index("ix_privacy_requests_org_status", "organization_id", "status"),)

"""SQLAlchemy models for Enterprise Governance, Risk Assessment & Human-in-the-Loop Approvals."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


class GovernancePolicyModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Tenant-specific or default versioned governance policies."""

    __tablename__ = "governance_policies"
    __table_args__ = (
        UniqueConstraint("organization_id", "policy_version", name="uq_gov_policy_org_version"),
        Index("ix_governance_policies_org_status", "organization_id", "status"),
    )

    policy_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="ACTIVE",
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class ApprovalRequestModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Human-in-the-loop approval request for governed operations."""

    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_requests_org_status", "organization_id", "status"),
        Index("ix_approval_requests_org_risk", "organization_id", "risk_level"),
        Index("ix_approval_requests_org_type", "organization_id", "request_type"),
    )

    request_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    risk_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    risk_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    context: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    action_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    resource_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    policy_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    votes: Mapped[list["ApprovalVoteModel"]] = relationship(
        "ApprovalVoteModel",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    decisions: Mapped[list["ApprovalDecisionModel"]] = relationship(
        "ApprovalDecisionModel",
        back_populates="request",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["ApprovalCommentModel"]] = relationship(
        "ApprovalCommentModel",
        back_populates="request",
        cascade="all, delete-orphan",
    )


class ApprovalVoteModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Reviewer vote submitted for an approval request."""

    __tablename__ = "approval_votes"
    __table_args__ = (
        UniqueConstraint(
            "approval_request_id", "reviewer_id", name="uq_approval_votes_req_reviewer"
        ),
    )

    approval_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    request: Mapped["ApprovalRequestModel"] = relationship(
        "ApprovalRequestModel",
        back_populates="votes",
    )


class ApprovalDecisionModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Immutable final decision record for an approval request."""

    __tablename__ = "approval_decisions"
    __table_args__ = (Index("ix_approval_decisions_org_request", "organization_id", "request_id"),)

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    reviewer_ids: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    policy_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    risk_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    decision_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    request: Mapped["ApprovalRequestModel"] = relationship(
        "ApprovalRequestModel",
        back_populates="decisions",
    )


class ApprovalCommentModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Review comment on an approval request."""

    __tablename__ = "approval_comments"
    __table_args__ = (Index("ix_approval_comments_request", "approval_request_id"),)

    approval_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    comment: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    request: Mapped["ApprovalRequestModel"] = relationship(
        "ApprovalRequestModel",
        back_populates="comments",
    )

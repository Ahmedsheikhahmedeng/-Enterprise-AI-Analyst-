from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import AnalysisRun
    from app.models.audit import AuditLog
    from app.models.conversation import Conversation
    from app.models.data_source import DataSource
    from app.models.dataset import Dataset
    from app.models.document import Document
    from app.models.report import Report
    from app.models.role import OrganizationMember, Role
    from app.models.usage import LLMRequest, UsageEvent


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Organization entity representing tenants in the multi-tenant architecture."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Tenant-scoped relationships (cascade deletion on organization removal)
    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    datasets: Mapped[list["Dataset"]] = relationship(
        "Dataset",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    data_sources: Mapped[list["DataSource"]] = relationship(
        "DataSource",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(
        "AnalysisRun",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    usage_events: Mapped[list["UsageEvent"]] = relationship(
        "UsageEvent",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    llm_requests: Mapped[list["LLMRequest"]] = relationship(
        "LLMRequest",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

"""SQLAlchemy models for Enterprise LLM Gateway and Model Governance."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, UUIDPrimaryKeyMixin


class TenantLLMPolicyModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Tenant-specific LLM governance policy enforcing model, cost, and provider limits."""

    __tablename__ = "tenant_llm_policies"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_tenant_llm_policies_org"),)

    allowed_providers: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    allowed_models: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    max_tokens_per_request: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    max_cost_per_request: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
    )
    allowed_capabilities: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    data_residency: Mapped[str] = mapped_column(
        String(50),
        default="ANY",
        nullable=False,
    )
    streaming_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    caching_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ModelDefinitionModel(Base, UUIDPrimaryKeyMixin):
    """Governed model registry entry defining approved LLM models, pricing, and capabilities."""

    __tablename__ = "llm_model_definitions"
    __table_args__ = (
        UniqueConstraint(
            "provider", "model_name", "model_version", name="uq_model_def_provider_name_ver"
        ),
        Index("ix_model_def_provider_name", "provider", "model_name"),
        Index("ix_model_def_status_approved", "status", "is_approved"),
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        default="latest",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="ACTIVE",
        nullable=False,
    )
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    capabilities: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    input_price_per_1k: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        default=Decimal("0.0"),
        nullable=False,
    )
    output_price_per_1k: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        default=Decimal("0.0"),
        nullable=False,
    )
    context_window: Mapped[int] = mapped_column(
        Integer,
        default=128000,
        nullable=False,
    )
    max_output_tokens: Mapped[int] = mapped_column(
        Integer,
        default=4096,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

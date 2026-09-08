"""SQLAlchemy models for Semantic Catalog, Business Glossary, Metrics, Dimensions, and Governance."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    desc,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.dataset import Dataset, DatasetColumn, DatasetVersion
    from app.models.organization import Organization
    from app.models.user import User


class BusinessTerm(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Business glossary term establishing canonical conceptual definitions."""

    __tablename__ = "business_terms"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_business_terms_org_name"),
        Index("ix_business_terms_org_norm_name", "organization_id", "normalized_name"),
        Index("ix_business_terms_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    steward: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    creator: Mapped["User | None"] = relationship("User")
    versions: Mapped[list["BusinessTermVersion"]] = relationship(
        "BusinessTermVersion",
        back_populates="term",
        cascade="all, delete-orphan",
        order_by=desc("version"),
    )


class BusinessTermVersion(Base, UUIDPrimaryKeyMixin):
    """Immutable version history for Business Glossary definitions."""

    __tablename__ = "business_term_versions"
    __table_args__ = (
        UniqueConstraint("term_id", "version", name="uq_term_versions_term_version"),
        Index("ix_term_versions_org_term", "organization_id", "term_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_terms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    term: Mapped["BusinessTerm"] = relationship("BusinessTerm", back_populates="versions")


class SemanticMetric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Semantic metric definition representing analytical formulas and aggregations."""

    __tablename__ = "semantic_metrics"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_semantic_metrics_org_name"),
        Index("ix_semantic_metrics_org_norm_name", "organization_id", "normalized_name"),
        Index("ix_semantic_metrics_org_dataset", "organization_id", "dataset_id"),
        Index("ix_semantic_metrics_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    formula: Mapped[str] = mapped_column(String(500), nullable=False)
    grain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    filters: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    aggregation: Mapped[str] = mapped_column(String(50), nullable=False)
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    dataset: Mapped["Dataset | None"] = relationship("Dataset")


class SemanticDimension(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Semantic dimension representing analytical grouping attributes."""

    __tablename__ = "semantic_dimensions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "name", name="uq_semantic_dimensions_dataset_name"),
        Index("ix_semantic_dimensions_org_norm", "organization_id", "normalized_name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_columns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False)
    hierarchy: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    dataset: Mapped["Dataset"] = relationship("Dataset")
    column: Mapped["DatasetColumn"] = relationship("DatasetColumn")


class SemanticEntity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Core domain business entity associated with physical datasets."""

    __tablename__ = "semantic_entities"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_semantic_entities_org_name"),
        Index("ix_semantic_entities_org_norm", "organization_id", "normalized_name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    primary_key: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name_column: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    dataset: Mapped["Dataset"] = relationship("Dataset")


class SemanticRelationship(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Semantic joins and cardinality relationships between business entities."""

    __tablename__ = "semantic_relationships"
    __table_args__ = (
        Index("ix_semantic_rel_org", "organization_id"),
        Index("ix_semantic_rel_from_to", "from_entity_id", "to_entity_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    from_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("semantic_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("semantic_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    from_column: Mapped[str] = mapped_column(String(100), nullable=False)
    to_column: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    from_entity: Mapped["SemanticEntity"] = relationship(
        "SemanticEntity", foreign_keys=[from_entity_id]
    )
    to_entity: Mapped["SemanticEntity"] = relationship(
        "SemanticEntity", foreign_keys=[to_entity_id]
    )


class SemanticSynonym(Base, UUIDPrimaryKeyMixin):
    """Multilingual synonyms connecting colloquial or localized words to concepts."""

    __tablename__ = "semantic_synonyms"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "semantic_object_type",
            "semantic_object_id",
            "normalized_synonym",
            name="uq_synonyms_org_obj_norm",
        ),
        Index("ix_synonyms_org_norm", "organization_id", "normalized_synonym"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    semantic_object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    semantic_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    synonym: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_synonym: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SemanticColumnMapping(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Physical binding between semantic concepts and dataset columns."""

    __tablename__ = "semantic_column_mappings"
    __table_args__ = (
        Index(
            "ix_col_map_org_obj", "organization_id", "semantic_object_type", "semantic_object_id"
        ),
        Index("ix_col_map_dataset_col", "dataset_id", "column_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    semantic_object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    semantic_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    column_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_columns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mapping_type: Mapped[str] = mapped_column(String(50), default="DIRECT", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    dataset: Mapped["Dataset"] = relationship("Dataset")
    column: Mapped["DatasetColumn"] = relationship("DatasetColumn")
    dataset_version: Mapped["DatasetVersion | None"] = relationship("DatasetVersion")


class SemanticConflict(Base, UUIDPrimaryKeyMixin):
    """Records detected semantic discrepancies and definition collisions."""

    __tablename__ = "semantic_conflicts"
    __table_args__ = (Index("ix_semantic_conflicts_org", "organization_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    object_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="MEDIUM", nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SemanticEmbedding(Base, UUIDPrimaryKeyMixin):
    """Tracks vector indexing metadata for semantic concepts in Qdrant."""

    __tablename__ = "semantic_embeddings"
    __table_args__ = (
        Index(
            "ix_semantic_embeddings_org_obj",
            "organization_id",
            "semantic_object_type",
            "semantic_object_id",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    semantic_object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    semantic_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    vector_id: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

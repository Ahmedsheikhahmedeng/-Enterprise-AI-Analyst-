"""SQLAlchemy models for Knowledge Graph Nodes, Edges, Aliases, Conflicts, and Versions."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class KnowledgeGraphNode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents a canonical vertex in the multi-tenant enterprise knowledge graph."""

    __tablename__ = "knowledge_graph_nodes"
    __table_args__ = (
        Index("ix_kg_nodes_org_type", "organization_id", "node_type"),
        Index("ix_kg_nodes_org_norm_name", "organization_id", "normalized_name"),
        Index(
            "ix_kg_nodes_org_source",
            "organization_id",
            "source_object_type",
            "source_object_id",
        ),
        Index("ix_kg_nodes_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    node_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    outbound_edges: Mapped[list["KnowledgeGraphEdge"]] = relationship(
        "KnowledgeGraphEdge",
        foreign_keys="KnowledgeGraphEdge.source_node_id",
        cascade="all, delete-orphan",
        back_populates="source_node",
    )
    inbound_edges: Mapped[list["KnowledgeGraphEdge"]] = relationship(
        "KnowledgeGraphEdge",
        foreign_keys="KnowledgeGraphEdge.target_node_id",
        cascade="all, delete-orphan",
        back_populates="target_node",
    )
    aliases: Mapped[list["KnowledgeGraphAlias"]] = relationship(
        "KnowledgeGraphAlias",
        cascade="all, delete-orphan",
        back_populates="entity_node",
    )


class KnowledgeGraphEdge(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents a directed typed relationship connecting two knowledge graph nodes."""

    __tablename__ = "knowledge_graph_edges"
    __table_args__ = (
        Index("ix_kg_edges_org_source", "organization_id", "source_node_id"),
        Index("ix_kg_edges_org_target", "organization_id", "target_node_id"),
        Index("ix_kg_edges_src_tgt_type", "source_node_id", "target_node_id", "edge_type"),
        Index("ix_kg_edges_org_verified_status", "organization_id", "is_verified", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    source_object_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_object_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    source_node: Mapped["KnowledgeGraphNode"] = relationship(
        "KnowledgeGraphNode",
        foreign_keys=[source_node_id],
        back_populates="outbound_edges",
    )
    target_node: Mapped["KnowledgeGraphNode"] = relationship(
        "KnowledgeGraphNode",
        foreign_keys=[target_node_id],
        back_populates="inbound_edges",
    )


class KnowledgeGraphAlias(Base, UUIDPrimaryKeyMixin):
    """Stores multilingual synonyms and aliases mapped to entity nodes."""

    __tablename__ = "knowledge_graph_aliases"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "entity_node_id",
            "normalized_alias",
            name="uq_kg_alias_org_node_norm",
        ),
        Index("ix_kg_alias_org_norm", "organization_id", "normalized_alias"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    entity_node: Mapped["KnowledgeGraphNode"] = relationship(
        "KnowledgeGraphNode",
        back_populates="aliases",
    )


class KnowledgeGraphConflict(Base, UUIDPrimaryKeyMixin):
    """Tracks structural collisions, competing joins, or incompatible graph paths."""

    __tablename__ = "knowledge_graph_conflicts"
    __table_args__ = (Index("ix_kg_conflicts_org_status", "organization_id", "status"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="MEDIUM", nullable=False)
    node_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    edge_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="OPEN", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )


class KnowledgeGraphVersion(Base, UUIDPrimaryKeyMixin):
    """Monotonically increasing graph version counter scoped per tenant organization."""

    __tablename__ = "knowledge_graph_versions"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_kg_version_org"),
        Index("ix_kg_version_org", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

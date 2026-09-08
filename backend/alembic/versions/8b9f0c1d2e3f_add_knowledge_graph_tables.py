"""add knowledge graph tables

Revision ID: 8b9f0c1d2e3f
Revises: 7a8e9b01c2d3
Create Date: 2026-09-07 11:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b9f0c1d2e3f"
down_revision: str | None = "7a8e9b01c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. knowledge_graph_nodes
    op.create_table(
        "knowledge_graph_nodes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("node_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("source_object_type", sa.String(length=50), nullable=False),
        sa.Column("source_object_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_graph_nodes_organization_id",
        "knowledge_graph_nodes",
        ["organization_id"],
    )
    op.create_index(
        "ix_kg_nodes_org_type",
        "knowledge_graph_nodes",
        ["organization_id", "node_type"],
    )
    op.create_index(
        "ix_kg_nodes_org_norm_name",
        "knowledge_graph_nodes",
        ["organization_id", "normalized_name"],
    )
    op.create_index(
        "ix_kg_nodes_org_source",
        "knowledge_graph_nodes",
        ["organization_id", "source_object_type", "source_object_id"],
    )
    op.create_index(
        "ix_kg_nodes_org_status",
        "knowledge_graph_nodes",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_knowledge_graph_nodes_source_object_id",
        "knowledge_graph_nodes",
        ["source_object_id"],
    )

    # 2. knowledge_graph_edges
    op.create_table(
        "knowledge_graph_edges",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("source_node_id", sa.UUID(), nullable=False),
        sa.Column("target_node_id", sa.UUID(), nullable=False),
        sa.Column("edge_type", sa.String(length=50), nullable=False),
        sa.Column("weight", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="draft", nullable=False),
        sa.Column("source_object_type", sa.String(length=50), nullable=True),
        sa.Column("source_object_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["source_node_id"], ["knowledge_graph_nodes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_node_id"], ["knowledge_graph_nodes.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_graph_edges_organization_id",
        "knowledge_graph_edges",
        ["organization_id"],
    )
    op.create_index(
        "ix_knowledge_graph_edges_source_node_id",
        "knowledge_graph_edges",
        ["source_node_id"],
    )
    op.create_index(
        "ix_knowledge_graph_edges_target_node_id",
        "knowledge_graph_edges",
        ["target_node_id"],
    )
    op.create_index(
        "ix_knowledge_graph_edges_source_object_id",
        "knowledge_graph_edges",
        ["source_object_id"],
    )
    op.create_index(
        "ix_kg_edges_org_source",
        "knowledge_graph_edges",
        ["organization_id", "source_node_id"],
    )
    op.create_index(
        "ix_kg_edges_org_target",
        "knowledge_graph_edges",
        ["organization_id", "target_node_id"],
    )
    op.create_index(
        "ix_kg_edges_src_tgt_type",
        "knowledge_graph_edges",
        ["source_node_id", "target_node_id", "edge_type"],
    )
    op.create_index(
        "ix_kg_edges_org_verified_status",
        "knowledge_graph_edges",
        ["organization_id", "is_verified", "status"],
    )

    # 3. knowledge_graph_aliases
    op.create_table(
        "knowledge_graph_aliases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("entity_node_id", sa.UUID(), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("normalized_alias", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=10), server_default="en", nullable=False),
        sa.Column("source", sa.String(length=50), server_default="user", nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["entity_node_id"], ["knowledge_graph_nodes.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "entity_node_id",
            "normalized_alias",
            name="uq_kg_alias_org_node_norm",
        ),
    )
    op.create_index(
        "ix_knowledge_graph_aliases_organization_id",
        "knowledge_graph_aliases",
        ["organization_id"],
    )
    op.create_index(
        "ix_knowledge_graph_aliases_entity_node_id",
        "knowledge_graph_aliases",
        ["entity_node_id"],
    )

    op.create_index(
        "ix_kg_alias_org_norm",
        "knowledge_graph_aliases",
        ["organization_id", "normalized_alias"],
    )

    # 4. knowledge_graph_conflicts
    op.create_table(
        "knowledge_graph_conflicts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=50), server_default="MEDIUM", nullable=False),
        sa.Column(
            "node_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "edge_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), server_default="OPEN", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_graph_conflicts_organization_id",
        "knowledge_graph_conflicts",
        ["organization_id"],
    )
    op.create_index(
        "ix_kg_conflicts_org_status",
        "knowledge_graph_conflicts",
        ["organization_id", "status"],
    )

    # 5. knowledge_graph_versions
    op.create_table(
        "knowledge_graph_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_kg_version_org"),
    )
    op.create_index(
        "ix_kg_version_org",
        "knowledge_graph_versions",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_table("knowledge_graph_versions")
    op.drop_table("knowledge_graph_conflicts")
    op.drop_table("knowledge_graph_aliases")
    op.drop_table("knowledge_graph_edges")
    op.drop_table("knowledge_graph_nodes")

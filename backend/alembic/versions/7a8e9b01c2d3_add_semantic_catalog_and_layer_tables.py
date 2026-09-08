"""add semantic catalog and layer tables

Revision ID: 7a8e9b01c2d3
Revises: 714182cbde59
Create Date: 2026-09-07 00:21:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a8e9b01c2d3"
down_revision: str | None = "714182cbde59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. business_terms
    op.create_table(
        "business_terms",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("steward", sa.String(length=255), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_business_terms_org_name"),
    )
    op.create_index("ix_business_terms_organization_id", "business_terms", ["organization_id"])
    op.create_index(
        "ix_business_terms_org_norm_name", "business_terms", ["organization_id", "normalized_name"]
    )
    op.create_index("ix_business_terms_org_status", "business_terms", ["organization_id", "status"])

    # 2. business_term_versions
    op.create_table(
        "business_term_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("term_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["business_terms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("term_id", "version", name="uq_term_versions_term_version"),
    )
    op.create_index(
        "ix_business_term_versions_organization_id", "business_term_versions", ["organization_id"]
    )
    op.create_index("ix_business_term_versions_term_id", "business_term_versions", ["term_id"])
    op.create_index(
        "ix_term_versions_org_term", "business_term_versions", ["organization_id", "term_id"]
    )

    # 3. semantic_metrics
    op.create_table(
        "semantic_metrics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("formula", sa.String(length=500), nullable=False),
        sa.Column("grain", sa.String(length=100), nullable=True),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("aggregation", sa.String(length=50), nullable=False),
        sa.Column("dataset_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_semantic_metrics_org_name"),
    )
    op.create_index("ix_semantic_metrics_organization_id", "semantic_metrics", ["organization_id"])
    op.create_index("ix_semantic_metrics_dataset_id", "semantic_metrics", ["dataset_id"])
    op.create_index(
        "ix_semantic_metrics_org_norm_name",
        "semantic_metrics",
        ["organization_id", "normalized_name"],
    )
    op.create_index(
        "ix_semantic_metrics_org_dataset", "semantic_metrics", ["organization_id", "dataset_id"]
    )
    op.create_index(
        "ix_semantic_metrics_org_status", "semantic_metrics", ["organization_id", "status"]
    )

    # 4. semantic_dimensions
    op.create_table(
        "semantic_dimensions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("column_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("data_type", sa.String(length=50), nullable=False),
        sa.Column("hierarchy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["column_id"], ["dataset_columns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "name", name="uq_semantic_dimensions_dataset_name"),
    )
    op.create_index(
        "ix_semantic_dimensions_organization_id", "semantic_dimensions", ["organization_id"]
    )
    op.create_index("ix_semantic_dimensions_dataset_id", "semantic_dimensions", ["dataset_id"])
    op.create_index("ix_semantic_dimensions_column_id", "semantic_dimensions", ["column_id"])
    op.create_index(
        "ix_semantic_dimensions_org_norm",
        "semantic_dimensions",
        ["organization_id", "normalized_name"],
    )

    # 5. semantic_entities
    op.create_table(
        "semantic_entities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("primary_key", sa.String(length=100), nullable=False),
        sa.Column("display_name_column", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_semantic_entities_org_name"),
    )
    op.create_index(
        "ix_semantic_entities_organization_id", "semantic_entities", ["organization_id"]
    )
    op.create_index("ix_semantic_entities_dataset_id", "semantic_entities", ["dataset_id"])
    op.create_index(
        "ix_semantic_entities_org_norm", "semantic_entities", ["organization_id", "normalized_name"]
    )

    # 6. semantic_relationships
    op.create_table(
        "semantic_relationships",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("from_entity_id", sa.UUID(), nullable=False),
        sa.Column("to_entity_id", sa.UUID(), nullable=False),
        sa.Column("relationship_type", sa.String(length=50), nullable=False),
        sa.Column("from_column", sa.String(length=100), nullable=False),
        sa.Column("to_column", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["from_entity_id"], ["semantic_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_entity_id"], ["semantic_entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_semantic_relationships_organization_id", "semantic_relationships", ["organization_id"]
    )
    op.create_index(
        "ix_semantic_relationships_from_entity_id", "semantic_relationships", ["from_entity_id"]
    )
    op.create_index(
        "ix_semantic_relationships_to_entity_id", "semantic_relationships", ["to_entity_id"]
    )
    op.create_index("ix_semantic_rel_org", "semantic_relationships", ["organization_id"])
    op.create_index(
        "ix_semantic_rel_from_to", "semantic_relationships", ["from_entity_id", "to_entity_id"]
    )

    # 7. semantic_synonyms
    op.create_table(
        "semantic_synonyms",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("semantic_object_type", sa.String(length=50), nullable=False),
        sa.Column("semantic_object_id", sa.UUID(), nullable=False),
        sa.Column("synonym", sa.String(length=255), nullable=False),
        sa.Column("normalized_synonym", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False, server_default="en"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "semantic_object_type",
            "semantic_object_id",
            "normalized_synonym",
            name="uq_synonyms_org_obj_norm",
        ),
    )
    op.create_index(
        "ix_semantic_synonyms_organization_id", "semantic_synonyms", ["organization_id"]
    )
    op.create_index(
        "ix_semantic_synonyms_semantic_object_id", "semantic_synonyms", ["semantic_object_id"]
    )
    op.create_index(
        "ix_synonyms_org_norm", "semantic_synonyms", ["organization_id", "normalized_synonym"]
    )

    # 8. semantic_column_mappings
    op.create_table(
        "semantic_column_mappings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("semantic_object_type", sa.String(length=50), nullable=False),
        sa.Column("semantic_object_id", sa.UUID(), nullable=False),
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("dataset_version_id", sa.UUID(), nullable=True),
        sa.Column("column_id", sa.UUID(), nullable=False),
        sa.Column("mapping_type", sa.String(length=50), nullable=False, server_default="DIRECT"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verified_by", sa.UUID(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["column_id"], ["dataset_columns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"], ["dataset_versions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_semantic_column_mappings_organization_id",
        "semantic_column_mappings",
        ["organization_id"],
    )
    op.create_index(
        "ix_semantic_column_mappings_dataset_id", "semantic_column_mappings", ["dataset_id"]
    )
    op.create_index(
        "ix_semantic_column_mappings_dataset_version_id",
        "semantic_column_mappings",
        ["dataset_version_id"],
    )
    op.create_index(
        "ix_semantic_column_mappings_column_id", "semantic_column_mappings", ["column_id"]
    )
    op.create_index(
        "ix_semantic_column_mappings_semantic_object_id",
        "semantic_column_mappings",
        ["semantic_object_id"],
    )
    op.create_index(
        "ix_col_map_org_obj",
        "semantic_column_mappings",
        ["organization_id", "semantic_object_type", "semantic_object_id"],
    )
    op.create_index(
        "ix_col_map_dataset_col", "semantic_column_mappings", ["dataset_id", "column_id"]
    )

    # 9. semantic_conflicts
    op.create_table(
        "semantic_conflicts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("object_type", sa.String(length=50), nullable=False),
        sa.Column("object_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False, server_default="MEDIUM"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_semantic_conflicts_organization_id", "semantic_conflicts", ["organization_id"]
    )
    op.create_index("ix_semantic_conflicts_org", "semantic_conflicts", ["organization_id"])

    # 10. semantic_embeddings
    op.create_table(
        "semantic_embeddings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("semantic_object_type", sa.String(length=50), nullable=False),
        sa.Column("semantic_object_id", sa.UUID(), nullable=False),
        sa.Column("vector_id", sa.String(length=255), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
        sa.Column("embedding_version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="completed"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_semantic_embeddings_organization_id", "semantic_embeddings", ["organization_id"]
    )
    op.create_index(
        "ix_semantic_embeddings_semantic_object_id", "semantic_embeddings", ["semantic_object_id"]
    )
    op.create_index(
        "ix_semantic_embeddings_org_obj",
        "semantic_embeddings",
        ["organization_id", "semantic_object_type", "semantic_object_id"],
    )


def downgrade() -> None:
    op.drop_table("semantic_embeddings")
    op.drop_table("semantic_conflicts")
    op.drop_table("semantic_column_mappings")
    op.drop_table("semantic_synonyms")
    op.drop_table("semantic_relationships")
    op.drop_table("semantic_entities")
    op.drop_table("semantic_dimensions")
    op.drop_table("semantic_metrics")
    op.drop_table("business_term_versions")
    op.drop_table("business_terms")

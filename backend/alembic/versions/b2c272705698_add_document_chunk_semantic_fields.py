"""add_document_chunk_semantic_fields

Revision ID: b2c272705698
Revises: fb0a9ae0683a
Create Date: 2026-09-05 13:30:16.121815

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c272705698"
down_revision: str | Sequence[str] | None = "fb0a9ae0683a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("document_chunks", sa.Column("parent_chunk_id", sa.UUID(), nullable=True))
    op.add_column("document_chunks", sa.Column("heading_context", sa.Text(), nullable=True))
    op.add_column(
        "document_chunks",
        sa.Column("heading_path", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("source_locator", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "document_chunks",
        sa.Column("character_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "document_chunks",
        sa.Column("content_hash", sa.String(length=64), server_default="", nullable=False),
    )
    op.add_column(
        "document_chunks",
        sa.Column("chunker_version", sa.String(length=50), server_default="1.0.0", nullable=False),
    )
    op.create_index(
        "ix_doc_chunks_org_hash",
        "document_chunks",
        ["organization_id", "content_hash"],
        unique=False,
    )
    op.create_index("ix_doc_chunks_parent", "document_chunks", ["parent_chunk_id"], unique=False)
    op.create_index(
        op.f("ix_document_chunks_content_hash"), "document_chunks", ["content_hash"], unique=False
    )
    op.create_foreign_key(
        "fk_document_chunks_parent_chunk_id",
        "document_chunks",
        "document_chunks",
        ["parent_chunk_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_document_chunks_parent_chunk_id", "document_chunks", type_="foreignkey")
    op.drop_index(op.f("ix_document_chunks_content_hash"), table_name="document_chunks")
    op.drop_index("ix_doc_chunks_parent", table_name="document_chunks")
    op.drop_index("ix_doc_chunks_org_hash", table_name="document_chunks")
    op.drop_column("document_chunks", "chunker_version")
    op.drop_column("document_chunks", "content_hash")
    op.drop_column("document_chunks", "character_count")
    op.drop_column("document_chunks", "token_count")
    op.drop_column("document_chunks", "source_locator")
    op.drop_column("document_chunks", "heading_path")
    op.drop_column("document_chunks", "heading_context")
    op.drop_column("document_chunks", "parent_chunk_id")
    # ### end Alembic commands ###

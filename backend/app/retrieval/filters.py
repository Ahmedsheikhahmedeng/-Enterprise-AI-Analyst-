"""Filter construction utilities for dense retrieval queries."""

import uuid
from typing import Any

from app.vectorstore.filters import TenantVectorFilterBuilder


class RetrievalFilterBuilder:
    """Builds tenant-isolated filter structures for vector store execution."""

    @classmethod
    def build_vector_filter(
        cls,
        organization_id: uuid.UUID,
        document_id: uuid.UUID | None = None,
        chunk_type: str | None = None,
        page_number: int | None = None,
        section: str | None = None,
    ) -> Any:
        """Construct Qdrant filter combining tenant isolation with optional metadata constraints."""
        return TenantVectorFilterBuilder.build_search_filter(
            organization_id=organization_id,
            document_id=document_id,
            chunk_type=chunk_type,
            page_number=page_number,
            section=section,
        )

    build_metadata_filter = build_vector_filter

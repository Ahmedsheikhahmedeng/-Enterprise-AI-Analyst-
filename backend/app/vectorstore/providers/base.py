"""Base interface protocol definition for vector store providers."""

import uuid
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from app.vectorstore.models import (
    IndexingBatchResult,
    SparseVector,
    VectorPoint,
    VectorSearchResult,
    VectorStoreStats,
)


@runtime_checkable
class VectorStore(Protocol):
    """Protocol defining vector store provider capabilities.

    Decouples application logic from specific vector engine SDKs.
    Every operation requires tenant scoping to guarantee multi-tenant boundaries.
    """

    async def ensure_collection(
        self,
        collection_name: str,
        vector_size: int,
        distance: str = "cosine",
        enable_sparse: bool = True,
    ) -> None:
        """Ensure collection exists and is configured compatibly."""
        ...

    async def upsert(
        self,
        collection_name: str,
        points: Sequence[VectorPoint],
    ) -> IndexingBatchResult:
        """Batch upsert points with strict tenant validation and concurrency throttling."""
        ...

    async def delete_by_document(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> int:
        """Delete all points belonging to a specific document under tenant scope."""
        ...

    async def delete_by_chunk(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        chunk_id: uuid.UUID,
    ) -> int:
        """Delete a single chunk vector under tenant scope."""
        ...

    async def delete_by_organization(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
    ) -> int:
        """Delete all vectors belonging to an organization in the collection."""
        ...

    async def get_points(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        point_ids: Sequence[uuid.UUID],
    ) -> list[VectorPoint]:
        """Retrieve points strictly scoped to the tenant."""
        ...

    async def count_points(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        document_id: uuid.UUID | None = None,
    ) -> int:
        """Count total vectors belonging to an organization (and optional document)."""
        ...

    async def get_collection_stats(
        self,
        collection_name: str,
    ) -> VectorStoreStats:
        """Retrieve statistics for the specified collection."""
        ...

    async def search(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        vector: Sequence[float],
        *,
        limit: int,
        score_threshold: float | None = None,
        filter_conditions: Any | None = None,
    ) -> list[VectorSearchResult]:
        """Perform dense vector similarity search strictly scoped to the tenant."""
        ...

    async def search_sparse(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        sparse_vector: SparseVector,
        *,
        limit: int,
        score_threshold: float | None = None,
        filter_conditions: Any | None = None,
    ) -> list[VectorSearchResult]:
        """Perform sparse vector similarity search strictly scoped to the tenant."""
        ...

    async def health_check(self) -> bool:
        """Check vector store engine connectivity."""
        ...

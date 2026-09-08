"""Domain VectorStoreService orchestrator."""

import logging
import uuid
from collections.abc import Sequence
from typing import Any

from app.vectorstore.collection import build_collection_name
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.exceptions import VectorStoreValidationError
from app.vectorstore.filters import TenantVectorFilterBuilder
from app.vectorstore.hashing import compute_vector_point_id
from app.vectorstore.models import (
    IndexingBatchResult,
    SparseVector,
    VectorPoint,
    VectorSearchResult,
    VectorStoreStats,
)
from app.vectorstore.payload import PayloadBuilder
from app.vectorstore.providers.base import VectorStore

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Enterprise domain service orchestrating vector store operations.

    Features:
    - Resolves deterministic collection names per embedding model configuration.
    - Ensures collections and schema indexes exist idempotently.
    - Constructs secure point IDs and payload schemas.
    - Enforces tenant isolation across all index and delete operations.
    """

    def __init__(
        self,
        config: VectorStoreConfig,
        provider: VectorStore,
    ) -> None:
        self.config = config
        self.provider = provider

    def get_collection_name(
        self,
        embedding_provider: str,
        embedding_model: str,
        dimensions: int,
        version: str,
    ) -> str:
        """Resolve deterministic collection name based on full embedding identity."""
        return build_collection_name(
            prefix=self.config.collection_prefix,
            provider=embedding_provider,
            model=embedding_model,
            dimensions=dimensions,
            version=version,
        )

    resolve_collection_name = get_collection_name

    async def ensure_collection(
        self,
        embedding_provider: str,
        embedding_model: str,
        dimensions: int,
        version: str,
        distance: str = "cosine",
        enable_sparse: bool = True,
    ) -> str:
        """Ensure collection exists with exact dimensions and payload indexes."""
        coll_name = self.get_collection_name(
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            dimensions=dimensions,
            version=version,
        )
        await self.provider.ensure_collection(
            collection_name=coll_name,
            vector_size=dimensions,
            distance=distance,
            enable_sparse=enable_sparse,
        )
        return coll_name

    async def upsert_document_chunks(
        self,
        organization_id: uuid.UUID,
        chunks: Sequence[Any],
        embeddings: Sequence[Any],
        vectors: Sequence[list[float]],
        sparse_vectors: Sequence[SparseVector | None] | None = None,
    ) -> IndexingBatchResult:
        """Batch index document chunks with tenant verification and payload schemas."""
        if not chunks:
            return IndexingBatchResult(
                collection_name="",
                total_points=0,
                successful_points=0,
                failed_points=0,
                status="success",
            )

        if len(chunks) != len(embeddings) or len(chunks) != len(vectors):
            raise VectorStoreValidationError(
                f"Mismatch in input lengths: chunks={len(chunks)}, "
                f"embeddings={len(embeddings)}, vectors={len(vectors)}."
            )

        first_emb = embeddings[0]
        coll_name = await self.ensure_collection(
            embedding_provider=getattr(first_emb, "provider", "local"),
            embedding_model=getattr(first_emb, "model", "default"),
            dimensions=getattr(first_emb, "dimensions", len(vectors[0])),
            version=getattr(first_emb, "version", "1.0.0"),
        )

        points: list[VectorPoint] = []
        for idx, (chunk, emb, vec) in enumerate(zip(chunks, embeddings, vectors, strict=True)):
            chunk_org_id = getattr(chunk, "organization_id", None)
            TenantVectorFilterBuilder.validate_tenant_consistency(organization_id, chunk_org_id)

            chunk_id = getattr(chunk, "id", None)
            if chunk_id is None:
                raise VectorStoreValidationError("Chunk is missing mandatory id.")
            emb_hash = getattr(emb, "embedding_input_hash", "")
            point_id = compute_vector_point_id(organization_id, chunk_id, emb_hash)

            content = getattr(chunk, "content", "")
            payload = PayloadBuilder.build_chunk_payload(
                chunk=chunk,
                embedding=emb,
                content=content,
            )

            sparse_vec = (
                sparse_vectors[idx] if sparse_vectors and idx < len(sparse_vectors) else None
            )

            points.append(
                VectorPoint(
                    id=point_id,
                    vector=vec,
                    payload=payload,
                    sparse_vector=sparse_vec,
                )
            )

        return await self.provider.upsert(
            collection_name=coll_name,
            points=points,
        )

    index_chunks = upsert_document_chunks

    async def delete_document_vectors(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> int:
        """Purge all vector points belonging to a document under tenant scope."""
        return await self.provider.delete_by_document(
            collection_name=collection_name,
            organization_id=organization_id,
            document_id=document_id,
        )

    async def delete_chunk_vector(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        chunk_id: uuid.UUID,
    ) -> int:
        """Purge a single chunk vector under tenant scope."""
        return await self.provider.delete_by_chunk(
            collection_name=collection_name,
            organization_id=organization_id,
            chunk_id=chunk_id,
        )

    async def get_stats(self, collection_name: str) -> VectorStoreStats:
        """Retrieve point counts and vector configuration statistics for a collection."""
        return await self.provider.get_collection_stats(collection_name)

    async def count_points(
        self,
        collection_name: str,
        organization_id: uuid.UUID,
        document_id: uuid.UUID | None = None,
    ) -> int:
        """Count total vectors belonging to an organization (and optional document)."""
        return await self.provider.count_points(
            collection_name=collection_name,
            organization_id=organization_id,
            document_id=document_id,
        )

    async def search_vectors(
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
        return await self.provider.search(
            collection_name=collection_name,
            organization_id=organization_id,
            vector=vector,
            limit=limit,
            score_threshold=score_threshold,
            filter_conditions=filter_conditions,
        )

    async def search_sparse_vectors(
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
        return await self.provider.search_sparse(
            collection_name=collection_name,
            organization_id=organization_id,
            sparse_vector=sparse_vector,
            limit=limit,
            score_threshold=score_threshold,
            filter_conditions=filter_conditions,
        )

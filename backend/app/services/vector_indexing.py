"""Application service orchestrating document vector indexing into Qdrant."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import BadRequestAppException, NotFoundAppException
from app.db.qdrant import create_qdrant_client
from app.embeddings.service import EmbeddingService
from app.models.document import DocumentChunkEmbedding
from app.repositories.chunk import DocumentChunkRepository
from app.repositories.document import DocumentRepository
from app.repositories.embedding import DocumentChunkEmbeddingRepository
from app.services.embedding_pipeline import create_default_embedding_service
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.hashing import compute_vector_point_id
from app.vectorstore.providers.qdrant import QdrantVectorStoreProvider
from app.vectorstore.schemas import DocumentIndexingResponse, DocumentIndexingStatusResponse
from app.vectorstore.service import VectorStoreService

logger = logging.getLogger("app.services.vector_indexing")


def create_default_vector_store_service(
    settings: Settings | None = None,
    qdrant_client: Any | None = None,
) -> VectorStoreService:
    """Instantiate a fully configured VectorStoreService."""
    s = settings or get_settings()
    cfg = VectorStoreConfig.from_settings(s)
    client = qdrant_client or create_qdrant_client(s)
    provider = QdrantVectorStoreProvider(client=client, config=cfg)
    return VectorStoreService(config=cfg, provider=provider)


class DocumentVectorIndexingService:
    """Orchestrates end-to-end dense vector indexing from PostgreSQL to Qdrant."""

    def __init__(
        self,
        document_repo: DocumentRepository | None = None,
        chunk_repo: DocumentChunkRepository | None = None,
        embedding_repo: DocumentChunkEmbeddingRepository | None = None,
        vectorstore_service: VectorStoreService | None = None,
        embedding_service: EmbeddingService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.document_repo = document_repo or DocumentRepository()
        self.chunk_repo = chunk_repo or DocumentChunkRepository()
        self.embedding_repo = embedding_repo or DocumentChunkEmbeddingRepository()
        self.settings = settings or get_settings()
        self.vectorstore = vectorstore_service or create_default_vector_store_service(self.settings)
        self.embedding_service = embedding_service or create_default_embedding_service(
            self.settings
        )

    async def index_document(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        force: bool = False,
    ) -> DocumentIndexingResponse:
        """Index all chunk vectors of a document with tenant isolation and idempotency."""
        # 1. Fetch document and verify tenant ownership

        doc = await self.document_repo.get_by_id(
            session=session,
            id=document_id,
            organization_id=organization_id,
        )
        if not doc:
            raise NotFoundAppException(
                message=f"Document {document_id} not found",
                code="DOCUMENT_NOT_FOUND",
            )

        # 2. Check document status: must be embedded or indexed
        if doc.status not in ("embedded", "indexing", "indexed"):
            raise BadRequestAppException(
                message=(
                    "Document must be in 'embedded' status before vector indexing. "
                    f"Current status: '{doc.status}'."
                ),
                code="INVALID_DOCUMENT_STATUS",
            )

        # 3. Retrieve chunks
        chunks = await self.chunk_repo.list_by_document(
            session=session,
            organization_id=organization_id,
            document_id=document_id,
            limit=10000,
        )
        if not chunks:
            raise BadRequestAppException(
                message=f"Document {document_id} has no chunks. Chunk and embed document first.",
                code="NO_CHUNKS_FOUND",
            )

        # 4. Retrieve embedding records
        embeddings = await self.embedding_repo.list_by_document(
            session=session,
            organization_id=organization_id,
            document_id=document_id,
            limit=10000,
        )
        if not embeddings:
            raise BadRequestAppException(
                message=f"Document {document_id} has no embedding metadata. Run embeddings first.",
                code="NO_EMBEDDINGS_FOUND",
            )

        # Map chunk_id to embedding record
        emb_by_chunk_id: dict[uuid.UUID, DocumentChunkEmbedding] = {
            e.chunk_id: e for e in embeddings if e.status == "completed"
        }
        valid_chunks = [c for c in chunks if c.id in emb_by_chunk_id]
        if not valid_chunks:
            raise BadRequestAppException(
                message="No completed chunk embeddings found for indexing.",
                code="INCOMPLETE_EMBEDDINGS",
            )

        valid_embeddings = [emb_by_chunk_id[c.id] for c in valid_chunks]

        # 5. Check if already fully indexed without force
        indexed_count = await self.embedding_repo.count_by_indexing_status(
            session=session,
            organization_id=organization_id,
            document_id=document_id,
            indexing_status="indexed",
        )
        first_emb = valid_embeddings[0]
        coll_name = self.vectorstore.resolve_collection_name(
            embedding_provider=first_emb.provider,
            embedding_model=first_emb.model,
            dimensions=first_emb.dimensions,
            version=first_emb.version,
        )

        if indexed_count >= len(valid_chunks) and not force:
            logger.info(
                "Document %s is already fully indexed (%d points) in collection '%s'.",
                document_id,
                indexed_count,
                coll_name,
            )
            return DocumentIndexingResponse(
                document_id=document_id,
                organization_id=organization_id,
                collection_name=coll_name,
                total_points=indexed_count,
                indexed_points=indexed_count,
                failed_points=0,
                latency_ms=0.0,
                status="vector_indexed",
            )

        # 6. Mark document as indexing
        doc.status = "indexing"
        await session.flush()

        try:
            # 7. Retrieve / Reconstruct dense vectors
            # Utilizing EmbeddingService ensures cache hits if vectors are cached
            batch_result = await self.embedding_service.embed_chunks(valid_chunks)
            vectors: list[list[float]] = []
            for it in batch_result.items:
                if it.vector is not None:
                    vectors.append(it.vector)
                else:
                    raise BadRequestAppException(
                        message=f"Failed to obtain vector for chunk '{it.chunk_id}': {it.error}",
                        code="VECTOR_GENERATION_FAILED",
                    )

            # 8. Index into Qdrant
            index_res = await self.vectorstore.index_chunks(
                organization_id=organization_id,
                chunks=valid_chunks,
                embeddings=valid_embeddings,
                vectors=vectors,
            )

            # 9. Transactional update of PostgreSQL indexing metadata
            now = datetime.now(UTC)
            failed_chunk_set = set(index_res.failed_chunk_ids)

            for chunk, emb in zip(valid_chunks, valid_embeddings, strict=True):
                if chunk.id not in failed_chunk_set:
                    pt_id = compute_vector_point_id(
                        organization_id=organization_id,
                        chunk_id=chunk.id,
                        embedding_input_hash=emb.embedding_input_hash,
                    )
                    await self.embedding_repo.update_indexing_status(
                        session=session,
                        embedding_id=emb.id,
                        organization_id=organization_id,
                        point_id=pt_id,
                        status="indexed",
                        indexed_at=now,
                    )
                else:
                    emb.indexing_status = "failed"

            # 10. Update Document status
            if index_res.status == "success":
                doc.status = "indexed"
                doc.failure_reason = None
            elif index_res.status == "partial":
                doc.status = "indexed"
                doc.failure_reason = "Partial vector indexing failure."
            else:
                doc.status = "failed"
                doc.failure_reason = "Vector indexing failed for all points."

            doc_meta = dict(doc.metadata_ or {})
            doc_meta["qdrant_indexed"] = index_res.status in ("success", "partial")
            doc_meta["qdrant_collection"] = index_res.collection_name
            doc_meta["qdrant_points_count"] = index_res.successful_points
            doc_meta["qdrant_indexed_at"] = now.isoformat()
            doc.metadata_ = doc_meta
            await session.flush()

            logger.info(
                "Document %s vector indexing completed (%d indexed, %d failed)",
                document_id,
                index_res.successful_points,
                index_res.failed_points,
            )

            return DocumentIndexingResponse(
                document_id=document_id,
                organization_id=organization_id,
                collection_name=index_res.collection_name,
                total_points=index_res.total_points,
                indexed_points=index_res.successful_points,
                failed_points=index_res.failed_points,
                latency_ms=index_res.latency_ms,
                status="vector_indexed" if index_res.status == "success" else "vector_failed",
            )

        except Exception as exc:
            logger.error("Vector indexing failed for document %s: %s", document_id, exc)
            doc.status = "failed"
            doc.failure_reason = f"Vector indexing error: {str(exc)[:255]}"
            await session.flush()
            raise

    async def get_document_index_status(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> DocumentIndexingStatusResponse:
        """Retrieve Qdrant vector index status and chunk coverage for a document."""
        doc = await self.document_repo.get_by_id(
            session=session,
            id=document_id,
            organization_id=organization_id,
        )
        if not doc:
            raise NotFoundAppException(
                message=f"Document {document_id} not found",
                code="DOCUMENT_NOT_FOUND",
            )

        total_chunks = await self.chunk_repo.count_by_document(
            session=session,
            organization_id=organization_id,
            document_id=document_id,
        )
        indexed_count = await self.embedding_repo.count_by_indexing_status(
            session=session,
            organization_id=organization_id,
            document_id=document_id,
            indexing_status="indexed",
        )

        doc_meta = doc.metadata_ or {}
        coll_name = str(doc_meta.get("qdrant_collection", ""))
        indexed_at_str = doc_meta.get("qdrant_indexed_at")
        indexed_at = datetime.fromisoformat(indexed_at_str) if indexed_at_str else None

        if doc.status == "indexed" or (total_chunks > 0 and indexed_count >= total_chunks):
            indexing_status = "vector_indexed"
        elif doc.status == "indexing":
            indexing_status = "vector_indexing"
        elif indexed_count > 0:
            indexing_status = "vector_partial"
        else:
            indexing_status = "vector_pending"

        return DocumentIndexingStatusResponse(
            document_id=document_id,
            organization_id=organization_id,
            collection_name=coll_name,
            total_chunks=total_chunks,
            indexed_chunks=indexed_count,
            pending_chunks=max(0, total_chunks - indexed_count),
            indexing_status=indexing_status,
            is_indexed=doc.status == "indexed",
            indexed_at=indexed_at,
        )

    async def delete_document_vectors(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> int:
        """Purge vectors for a document from Qdrant."""
        doc = await self.document_repo.get_by_id(
            session=session,
            id=document_id,
            organization_id=organization_id,
        )
        if not doc:
            return 0

        doc_meta = doc.metadata_ or {}
        coll_name = doc_meta.get("qdrant_collection")
        if not coll_name:
            return 0

        deleted = await self.vectorstore.delete_document_vectors(
            collection_name=coll_name,
            organization_id=organization_id,
            document_id=document_id,
        )
        return deleted

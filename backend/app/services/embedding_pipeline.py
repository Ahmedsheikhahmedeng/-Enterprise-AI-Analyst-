"""Application service orchestrating document embedding generation, validation, and persistence."""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import BadRequestAppException, NotFoundAppException
from app.embeddings.cache import (
    EmbeddingCache,
    InMemoryEmbeddingCache,
    NoopEmbeddingCache,
    RedisEmbeddingCache,
)
from app.embeddings.config import EmbeddingConfig
from app.embeddings.providers.factory import EmbeddingProviderFactory
from app.embeddings.service import EmbeddingService
from app.models.document import DocumentChunkEmbedding
from app.repositories.chunk import DocumentChunkRepository
from app.repositories.document import DocumentRepository
from app.repositories.embedding import DocumentChunkEmbeddingRepository
from app.schemas.embedding import DocumentEmbeddingSummaryResponse

logger = logging.getLogger("app.services.embedding_pipeline")


def create_default_embedding_service(
    settings: Settings | None = None,
    redis_client: Any | None = None,
) -> EmbeddingService:
    """Create a fully configured EmbeddingService based on application settings."""
    cfg = EmbeddingConfig.from_settings(settings)
    provider = EmbeddingProviderFactory.create(cfg)

    cache: EmbeddingCache
    if cfg.cache_enabled:
        if redis_client is not None:
            cache = RedisEmbeddingCache(redis_client, default_ttl=cfg.cache_ttl_seconds)
        else:
            cache = InMemoryEmbeddingCache()
    else:
        cache = NoopEmbeddingCache()

    return EmbeddingService(config=cfg, provider=provider, cache=cache)


class DocumentEmbeddingPipelineService:
    """Orchestrates embedding creation, validation, tenant isolation, and metadata persistence."""

    def __init__(
        self,
        document_repo: DocumentRepository | None = None,
        chunk_repo: DocumentChunkRepository | None = None,
        embedding_repo: DocumentChunkEmbeddingRepository | None = None,
        embedding_service: EmbeddingService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.document_repo = document_repo or DocumentRepository()
        self.chunk_repo = chunk_repo or DocumentChunkRepository()
        self.embedding_repo = embedding_repo or DocumentChunkEmbeddingRepository()
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or create_default_embedding_service(
            self.settings
        )

    async def process_document_embeddings(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        force: bool = False,
    ) -> DocumentEmbeddingSummaryResponse:
        """Embed all chunks of a document with tenant isolation, idempotency, and persistence."""

        # 1. Fetch document and verify tenant isolation
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

        # 2. Check document status: must be chunked or embedded
        if doc.status not in ("chunked", "embedded", "embedding"):
            raise BadRequestAppException(
                message=(
                    "Document must be in 'chunked' or 'embedded' status before embedding. "
                    f"Current status: '{doc.status}'."
                ),
                code="INVALID_DOCUMENT_STATUS",
            )

        # 3. Retrieve document chunks
        chunks = await self.chunk_repo.list_by_document(
            session=session,
            organization_id=organization_id,
            document_id=document_id,
            limit=10000,
        )
        if not chunks:
            raise BadRequestAppException(
                message=f"Document {document_id} has no chunks. Please chunk document first.",
                code="NO_CHUNKS_FOUND",
            )

        # 4. Check for existing embeddings if force is False
        existing_count = await self.embedding_repo.count_by_document(
            session=session,
            organization_id=organization_id,
            document_id=document_id,
            status="completed",
        )
        if existing_count >= len(chunks) and not force:
            logger.info(
                "Document %s already has %d completed embeddings. Returning existing state.",
                document_id,
                existing_count,
            )
            # Return current summary without re-embedding
            norm_mode = "l2" if self.embedding_service.config.normalize else "none"
            return DocumentEmbeddingSummaryResponse(
                document_id=document_id,
                organization_id=organization_id,
                provider=self.embedding_service.provider.provider_name,
                model=self.embedding_service.config.model,
                version=self.embedding_service.config.version,
                dimensions=self.embedding_service.config.dimensions,
                normalization=norm_mode,
                total_embeddings=existing_count,
                completed_count=existing_count,
                failed_count=0,
                total_tokens=sum(c.token_count for c in chunks),
                latency_ms=0.0,
                cache_hits=existing_count,
                cache_misses=0,
                estimated_cost=0.0,
            )

        # 5. Mark document status as embedding
        doc.status = "embedding"
        await session.flush()

        try:
            # 6. Execute batch embedding via EmbeddingService
            batch_result = await self.embedding_service.embed_chunks(chunks)

            # 7. Idempotent database replacement: delete previous embeddings
            await self.embedding_repo.delete_by_document(
                session=session,
                organization_id=organization_id,
                document_id=document_id,
            )

            # 8. Create DocumentChunkEmbedding records
            norm_mode = "l2" if self.embedding_service.config.normalize else "none"
            db_embeddings: list[DocumentChunkEmbedding] = []
            for item in batch_result.items:
                if item.chunk_id is None:
                    continue
                db_emb = DocumentChunkEmbedding(
                    id=uuid.uuid4(),
                    organization_id=organization_id,
                    document_id=document_id,
                    chunk_id=item.chunk_id,
                    provider=self.embedding_service.provider.provider_name,
                    model=self.embedding_service.config.model,
                    version=self.embedding_service.config.version,
                    dimensions=self.embedding_service.config.dimensions,
                    normalization=norm_mode,
                    embedding_input_hash=item.embedding_input_hash,
                    token_count=item.token_count,
                    status="completed" if item.is_success else "failed",
                    failure_reason=item.error,
                )
                db_embeddings.append(db_emb)

            # 9. Bulk persist embedding metadata
            await self.embedding_repo.bulk_create(session=session, embeddings=db_embeddings)

            # 10. Update document status and metadata
            if batch_result.status in ("success", "partial"):
                doc.status = "embedded"
                doc.failure_reason = None
            else:
                doc.status = "failed"
                doc.failure_reason = "Embedding generation failed for all chunks."

            doc_meta = dict(doc.metadata_ or {})
            doc_meta["embedding_provider"] = self.embedding_service.provider.provider_name
            doc_meta["embedding_model"] = self.embedding_service.config.model
            doc_meta["embedding_version"] = self.embedding_service.config.version
            doc_meta["embedding_dimensions"] = self.embedding_service.config.dimensions
            doc_meta["embedding_count"] = batch_result.success_count
            if batch_result.metrics:
                doc_meta["embedding_metrics"] = {
                    "latency_ms": batch_result.metrics.latency_ms,
                    "total_tokens": batch_result.metrics.total_input_tokens,
                    "cache_hits": batch_result.metrics.cache_hits,
                    "cache_misses": batch_result.metrics.cache_misses,
                    "estimated_cost": batch_result.metrics.estimated_cost,
                }
            doc.metadata_ = doc_meta
            await session.flush()

            metrics = batch_result.metrics
            return DocumentEmbeddingSummaryResponse(
                document_id=document_id,
                organization_id=organization_id,
                provider=self.embedding_service.provider.provider_name,
                model=self.embedding_service.config.model,
                version=self.embedding_service.config.version,
                dimensions=self.embedding_service.config.dimensions,
                normalization=norm_mode,
                total_embeddings=len(db_embeddings),
                completed_count=batch_result.success_count,
                failed_count=batch_result.failed_count,
                total_tokens=metrics.total_input_tokens if metrics else 0,
                latency_ms=metrics.latency_ms if metrics else 0.0,
                cache_hits=metrics.cache_hits if metrics else 0,
                cache_misses=metrics.cache_misses if metrics else 0,
                estimated_cost=metrics.estimated_cost if metrics else None,
            )

        except Exception as exc:
            logger.error("Embedding pipeline failed for document %s: %s", document_id, exc)
            doc.status = "failed"
            doc.failure_reason = f"Embedding pipeline error: {str(exc)[:255]}"
            await session.flush()
            raise

"""Application service orchestrating document chunking, validation, and persistence."""

import logging
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.chunking.config import ChunkingConfig, default_chunking_config
from app.chunking.exceptions import ChunkingError, ChunkingPersistenceError
from app.chunking.metrics import compute_quality_summary
from app.chunking.models import ChunkQualitySummary, IntermediateChunk
from app.chunking.service import ChunkingService, default_chunking_service
from app.core.exceptions import BadRequestAppException, NotFoundAppException
from app.ingestion.service import IngestionService
from app.models.document import DocumentChunk
from app.repositories.chunk import DocumentChunkRepository
from app.repositories.document import DocumentRepository
from app.storage import StorageProvider, get_storage_provider

logger = logging.getLogger("app.services.chunking")


def _make_json_safe(val: Any) -> Any:
    """Recursively convert UUIDs and non-primitive objects to JSON-serializable primitives."""
    if isinstance(val, dict):
        return {str(k): _make_json_safe(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_make_json_safe(v) for v in val]
    if isinstance(val, uuid.UUID):
        return str(val)
    return val


class DocumentChunkService:
    """Orchestrates the chunking pipeline for enterprise documents."""

    def __init__(
        self,
        document_repo: DocumentRepository | None = None,
        chunk_repo: DocumentChunkRepository | None = None,
        chunking_service: ChunkingService | None = None,
        storage_provider: StorageProvider | None = None,
        config: ChunkingConfig = default_chunking_config,
    ) -> None:
        self.document_repo = document_repo or DocumentRepository()
        self.chunk_repo = chunk_repo or DocumentChunkRepository()
        self.chunking_service = chunking_service or default_chunking_service
        self.storage = storage_provider or get_storage_provider()
        self.config = config

    async def process_document_chunking(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> ChunkQualitySummary:
        """Execute structure-aware chunking, validation, and idempotent persistence."""
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

        # 2. Status check: document must be parsed (or re-chunked if already chunked)
        if doc.status not in ("parsed", "chunked"):
            raise BadRequestAppException(
                message=(
                    "Document must be in 'parsed' or 'chunked' status before chunking. "
                    f"Current status: '{doc.status}'."
                ),
                code="INVALID_DOCUMENT_STATUS",
            )

        # 3. Retrieve canonical parsed document
        ingestion_service = IngestionService(db_session=session, storage=self.storage)
        parsed_doc = await ingestion_service.get_parsed_document(
            organization_id=organization_id,
            document_id=document_id,
        )
        if not parsed_doc:
            raise NotFoundAppException(
                message=f"Parsed artifact for document {document_id} not found in storage.",
                code="PARSED_DOCUMENT_NOT_FOUND",
            )

        # 4. Mark status as chunking
        doc.status = "chunking"
        await session.flush()

        try:
            # 5. Execute in-memory structure analysis & chunking
            chunks, summary = self.chunking_service.chunk_document(
                parsed_doc=parsed_doc,
                organization_id=organization_id,
            )

            # 6. Idempotent database replacement: delete old chunks first
            await self.chunk_repo.delete_by_document(
                session=session,
                organization_id=organization_id,
                document_id=document_id,
            )

            # 7. Convert intermediate chunks to ORM models
            db_chunks: list[DocumentChunk] = []
            for c in chunks:
                chunk_type_str = (
                    c.chunk_type.value if hasattr(c.chunk_type, "value") else str(c.chunk_type)
                )
                db_chunk = DocumentChunk(
                    id=c.id,
                    organization_id=organization_id,
                    document_id=document_id,
                    parent_chunk_id=c.parent_chunk_id,
                    chunk_index=c.chunk_index,
                    chunk_type=chunk_type_str,
                    content=c.content,
                    heading_context=c.heading_context,
                    heading_path=c.heading_path,
                    page_number=c.page_number,
                    section=c.section,
                    source_locator=_make_json_safe(c.source_locator),
                    token_count=c.token_count,
                    character_count=c.character_count,
                    content_hash=c.content_hash,
                    chunker_version=c.chunker_version,
                    metadata_=_make_json_safe(c.metadata),
                )
                db_chunks.append(db_chunk)

            # 8. Bulk insert
            await self.chunk_repo.bulk_create(session=session, chunks=db_chunks)

            # 9. Update document metadata and status
            doc.status = "chunked"
            doc.failure_reason = None
            doc_meta = dict(doc.metadata_ or {})
            doc_meta["chunk_count"] = len(chunks)
            doc_meta["chunker_version"] = summary.chunker_version
            doc_meta["chunk_quality_summary"] = summary.model_dump(mode="json")
            doc.metadata_ = _make_json_safe(doc_meta)
            await session.flush()

            logger.info(
                "Document %s successfully chunked into %d chunks (tenant: %s)",
                document_id,
                len(chunks),
                organization_id,
            )
            return summary

        except ChunkingError as err:
            logger.error("Chunking failed for document %s: %s", document_id, err.message)
            doc.status = "failed"
            doc.failure_reason = f"Chunking error: {err.message}"
            await session.flush()
            raise BadRequestAppException(
                message=f"Document chunking failed: {err.message}",
                code="CHUNKING_FAILED",
            ) from err
        except Exception as exc:
            logger.exception("Unexpected error during chunking for document %s", document_id)
            doc.status = "failed"
            doc.failure_reason = "Internal chunking persistence failure"
            await session.flush()
            raise ChunkingPersistenceError(
                f"Failed to persist chunks for document {document_id}"
            ) from exc

    async def list_chunks(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        parent_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[DocumentChunk], int]:
        """List chunks for a document scoped to tenant."""
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

        chunks = await self.chunk_repo.list_by_document(
            session=session,
            organization_id=organization_id,
            document_id=document_id,
            parent_only=parent_only,
            skip=skip,
            limit=limit,
        )
        total = await self.chunk_repo.count_by_document(
            session=session,
            organization_id=organization_id,
            document_id=document_id,
            parent_only=parent_only,
        )
        return chunks, total

    async def get_chunk_summary(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> ChunkQualitySummary:
        """Retrieve quality summary for a document's chunks."""
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

        if doc.metadata_ and "chunk_quality_summary" in doc.metadata_:
            return ChunkQualitySummary.model_validate(doc.metadata_["chunk_quality_summary"])

        # Otherwise compute from existing chunks in database
        all_chunks = await self.chunk_repo.list_by_document(
            session=session,
            organization_id=organization_id,
            document_id=document_id,
            limit=10000,
        )
        intermediate: list[IntermediateChunk] = []
        for ch in all_chunks:
            intermediate.append(
                IntermediateChunk(
                    id=ch.id,
                    document_id=ch.document_id,
                    organization_id=ch.organization_id,
                    parent_chunk_id=ch.parent_chunk_id,
                    chunk_index=ch.chunk_index,
                    chunk_type=ch.chunk_type or "text",  # type: ignore[arg-type]
                    content=ch.content,
                    heading_context=ch.heading_context,
                    heading_path=ch.heading_path or [],
                    page_number=ch.page_number,
                    section=ch.section,
                    source_locator=ch.source_locator or {},
                    token_count=ch.token_count,
                    character_count=ch.character_count,
                    content_hash=ch.content_hash,
                    chunker_version=ch.chunker_version,
                    metadata=ch.metadata_ or {},
                )
            )
        return compute_quality_summary(
            chunks=intermediate,
            document_id=document_id,
            organization_id=organization_id,
            config=self.config,
        )

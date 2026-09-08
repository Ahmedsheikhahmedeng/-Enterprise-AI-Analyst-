"""Background worker for asynchronous document embedding generation jobs."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.embedding import DocumentEmbeddingSummaryResponse
from app.services.embedding_pipeline import DocumentEmbeddingPipelineService
from app.workers.ingestion import get_worker_session_factory

logger = logging.getLogger("app.workers.embedding")


class EmbeddingWorker:
    """Worker handling asynchronous document embedding generation."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.session_factory = session_factory or get_worker_session_factory()

    async def process_document(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        force: bool = False,
    ) -> DocumentEmbeddingSummaryResponse:
        """Process embeddings for a document in its own dedicated session."""
        async with self.session_factory() as session:
            service = DocumentEmbeddingPipelineService()
            summary = await service.process_document_embeddings(
                session=session,
                organization_id=organization_id,
                document_id=document_id,
                force=force,
            )
            await session.commit()
            return summary


async def run_embedding_job(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    force: bool = False,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Background task runner entrypoint for document embeddings."""
    worker = EmbeddingWorker(session_factory=session_factory)
    try:
        await worker.process_document(
            organization_id=organization_id,
            document_id=document_id,
            force=force,
        )
    except Exception:
        logger.exception(
            "Background embedding job failed for document %s (tenant: %s)",
            document_id,
            organization_id,
        )

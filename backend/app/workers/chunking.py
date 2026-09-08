"""Background worker for asynchronous document chunking jobs."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chunking.models import ChunkQualitySummary
from app.services.chunking import DocumentChunkService
from app.storage import StorageProvider, get_storage_provider
from app.workers.ingestion import get_worker_session_factory

logger = logging.getLogger("app.workers.chunking")


class ChunkingWorker:
    """Worker handling asynchronous document chunking execution."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        storage_provider: StorageProvider | None = None,
    ) -> None:
        self.session_factory = session_factory or get_worker_session_factory()
        self.storage = storage_provider or get_storage_provider()

    async def process_document(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> ChunkQualitySummary:
        """Process chunking for a document in its own dedicated session."""
        async with self.session_factory() as session:
            service = DocumentChunkService(storage_provider=self.storage)
            summary = await service.process_document_chunking(
                session=session,
                organization_id=organization_id,
                document_id=document_id,
            )
            await session.commit()
            return summary


async def run_chunking_job(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    storage_provider: StorageProvider | None = None,
) -> None:
    """Background task runner entrypoint for document chunking."""
    worker = ChunkingWorker(
        session_factory=session_factory,
        storage_provider=storage_provider,
    )
    try:
        await worker.process_document(
            organization_id=organization_id,
            document_id=document_id,
        )
    except Exception:
        logger.exception(
            "Background chunking job failed for document %s (tenant: %s)",
            document_id,
            organization_id,
        )

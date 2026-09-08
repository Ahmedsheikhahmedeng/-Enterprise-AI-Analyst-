"""Background worker for asynchronous document vector indexing jobs."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.vector_indexing import DocumentVectorIndexingService
from app.vectorstore.schemas import DocumentIndexingResponse
from app.workers.ingestion import get_worker_session_factory

logger = logging.getLogger("app.workers.vector_indexing")


class VectorIndexingWorker:
    """Worker handling background vector indexing of documents."""

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
    ) -> DocumentIndexingResponse:
        """Execute document vector indexing in dedicated session."""
        async with self.session_factory() as session:
            service = DocumentVectorIndexingService()
            result = await service.index_document(
                session=session,
                organization_id=organization_id,
                document_id=document_id,
                force=force,
            )
            await session.commit()
            return result


async def run_vector_indexing_job(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    force: bool = False,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Background task runner entrypoint for vector indexing."""
    worker = VectorIndexingWorker(session_factory=session_factory)
    try:
        await worker.process_document(
            organization_id=organization_id,
            document_id=document_id,
            force=force,
        )
    except Exception:
        logger.exception(
            "Background vector indexing job failed for document %s (tenant: %s)",
            document_id,
            organization_id,
        )

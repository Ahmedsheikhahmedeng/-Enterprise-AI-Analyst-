"""Background ingestion worker processing document parsing tasks asynchronously."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.postgres import create_database_engine, create_session_factory
from app.ingestion.models import ParsedDocument
from app.ingestion.service import IngestionService
from app.storage import StorageProvider, get_storage_provider

logger = logging.getLogger("app.workers.ingestion")

_worker_engine: AsyncEngine | None = None
_worker_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_worker_session_factory() -> async_sessionmaker[AsyncSession]:
    """Retrieve or initialize singleton session factory for background worker tasks."""
    global _worker_engine, _worker_session_factory
    if _worker_session_factory is None:
        settings = get_settings()
        _worker_engine = create_database_engine(settings)
        _worker_session_factory = create_session_factory(_worker_engine)
    return _worker_session_factory


class IngestionWorker:
    """Worker processing queued document ingestion jobs."""

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
    ) -> ParsedDocument:
        """Process a single document ingestion job with its own dedicated database session."""
        async with self.session_factory() as session:
            service = IngestionService(db_session=session, storage=self.storage)
            return await service.ingest_document(
                organization_id=organization_id,
                document_id=document_id,
            )


async def run_ingestion_job(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    storage_provider: StorageProvider | None = None,
) -> None:
    """Entrypoint invoked by background task runner or message consumer."""
    worker = IngestionWorker(
        session_factory=session_factory,
        storage_provider=storage_provider,
    )
    try:
        await worker.process_document(
            organization_id=organization_id,
            document_id=document_id,
        )
    except Exception as exc:
        logger.warning(
            "Ingestion job failed in worker execution",
            extra={
                "document_id": str(document_id),
                "organization_id": str(organization_id),
                "error": str(exc),
            },
        )

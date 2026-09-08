"""Task adapter for background document vector indexing."""

import uuid
from typing import Any

from app.jobs.context import JobContext
from app.jobs.exceptions import JobCancellationError, NonRetryableJobError
from app.workers.vector_indexing import VectorIndexingWorker


class VectorIndexingTask:
    """Adapts VectorIndexingWorker into standard TaskHandler interface."""

    def __init__(self, worker: VectorIndexingWorker | None = None) -> None:
        self.worker = worker or VectorIndexingWorker()

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        """Execute vector indexing idempotently with tenant filtering."""
        raw_doc_id = payload.get("document_id")
        if not raw_doc_id:
            raise NonRetryableJobError("Missing required 'document_id' in job payload")

        try:
            document_id = uuid.UUID(str(raw_doc_id))
        except ValueError as exc:
            raise NonRetryableJobError(f"Invalid document_id format: {raw_doc_id}") from exc

        force = bool(payload.get("force", False))

        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        context.report_progress(0.2, "Indexing embeddings into Qdrant collection")

        result = await self.worker.process_document(
            organization_id=context.organization_id,
            document_id=document_id,
            force=force,
        )

        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        context.report_progress(1.0, "Vector indexing completed")

        return {
            "document_id": str(document_id),
            "status": "completed",
            "indexed_points": getattr(result, "indexed_points", 0),
            "collection_name": getattr(result, "collection_name", "documents"),
        }

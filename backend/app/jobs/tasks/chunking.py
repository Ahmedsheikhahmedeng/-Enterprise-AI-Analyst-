"""Task adapter for background document chunking."""

import uuid
from typing import Any

from app.jobs.context import JobContext
from app.jobs.exceptions import JobCancellationError, NonRetryableJobError
from app.workers.chunking import ChunkingWorker


class ChunkingTask:
    """Adapts ChunkingWorker into standard TaskHandler interface."""

    def __init__(self, worker: ChunkingWorker | None = None) -> None:
        self.worker = worker or ChunkingWorker()

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        """Execute document chunking pipeline."""
        raw_doc_id = payload.get("document_id")
        if not raw_doc_id:
            raise NonRetryableJobError("Missing required 'document_id' in job payload")

        try:
            document_id = uuid.UUID(str(raw_doc_id))
        except ValueError as exc:
            raise NonRetryableJobError(f"Invalid document_id format: {raw_doc_id}") from exc

        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        context.report_progress(0.2, "Executing semantic and fixed chunking")

        summary = await self.worker.process_document(
            organization_id=context.organization_id,
            document_id=document_id,
        )

        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        context.report_progress(1.0, "Chunking completed")

        return {
            "document_id": str(document_id),
            "status": "completed",
            "chunks_created": getattr(summary, "total_chunks", 0),
            "avg_chunk_size": getattr(summary, "avg_chunk_size", 0.0),
        }

"""Task adapter for background document ingestion."""

import uuid
from typing import Any

from app.jobs.context import JobContext
from app.jobs.exceptions import JobCancellationError, NonRetryableJobError
from app.workers.ingestion import IngestionWorker


class DocumentIngestionTask:
    """Adapts IngestionWorker into standard TaskHandler interface."""

    def __init__(self, worker: IngestionWorker | None = None) -> None:
        self.worker = worker or IngestionWorker()

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        """Execute document ingestion pipeline with progress and cancellation checkpoints."""
        raw_doc_id = payload.get("document_id")
        if not raw_doc_id:
            raise NonRetryableJobError("Missing required 'document_id' in job payload")

        try:
            document_id = uuid.UUID(str(raw_doc_id))
        except ValueError as exc:
            raise NonRetryableJobError(f"Invalid document_id format: {raw_doc_id}") from exc

        # Safe checkpoint 1
        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        context.report_progress(0.1, "Initializing document parsing")

        # Process document
        parsed_doc = await self.worker.process_document(
            organization_id=context.organization_id,
            document_id=document_id,
        )

        # Safe checkpoint 2
        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        context.report_progress(1.0, "Document ingestion completed")

        return {
            "document_id": str(document_id),
            "status": "completed",
            "page_count": getattr(parsed_doc, "page_count", 1),
            "title": getattr(parsed_doc, "title", "Untitled"),
        }

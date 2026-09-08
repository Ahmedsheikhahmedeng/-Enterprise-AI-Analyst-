"""Task adapter for background document embedding generation."""

import uuid
from typing import Any

from app.jobs.context import JobContext
from app.jobs.exceptions import JobCancellationError, NonRetryableJobError
from app.workers.embedding import EmbeddingWorker


class EmbeddingTask:
    """Adapts EmbeddingWorker into standard TaskHandler interface."""

    def __init__(self, worker: EmbeddingWorker | None = None) -> None:
        self.worker = worker or EmbeddingWorker()

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        """Execute embedding generation with batching and idempotency checks."""
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

        context.report_progress(0.2, "Generating dense and sparse embeddings")

        summary = await self.worker.process_document(
            organization_id=context.organization_id,
            document_id=document_id,
            force=force,
        )

        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        context.report_progress(1.0, "Embedding generation completed")

        return {
            "document_id": str(document_id),
            "status": "completed",
            "embeddings_generated": getattr(summary, "embeddings_generated", 0),
            "model_name": getattr(summary, "model_name", "unknown"),
        }

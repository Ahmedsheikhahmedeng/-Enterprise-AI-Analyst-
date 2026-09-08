"""Task handlers package and auto-registration into task_registry."""

from app.jobs.registry import task_registry
from app.jobs.schemas import JobType
from app.jobs.tasks.agent import AgentExecutionTask
from app.jobs.tasks.chunking import ChunkingTask
from app.jobs.tasks.dataset_ingestion import DatasetIngestionTask
from app.jobs.tasks.embeddings import EmbeddingTask
from app.jobs.tasks.evaluation import EvaluationTask
from app.jobs.tasks.ingestion import DocumentIngestionTask
from app.jobs.tasks.report_export import ReportExportTask
from app.jobs.tasks.sync import DataSourceSyncTask
from app.jobs.tasks.vector_indexing import VectorIndexingTask


def register_default_tasks() -> None:
    """Register all standard task handlers in the global task registry."""
    task_registry.register(JobType.DOCUMENT_INGESTION.value, DocumentIngestionTask)
    task_registry.register(JobType.CHUNKING.value, ChunkingTask)
    task_registry.register(JobType.EMBEDDING.value, EmbeddingTask)
    task_registry.register(JobType.VECTOR_INDEXING.value, VectorIndexingTask)
    task_registry.register(JobType.EVALUATION.value, EvaluationTask)
    task_registry.register(JobType.REPORT_EXPORT.value, ReportExportTask)
    task_registry.register(JobType.AGENT_EXECUTION.value, AgentExecutionTask)
    task_registry.register(JobType.DATA_SOURCE_SYNC.value, DataSourceSyncTask)
    task_registry.register(JobType.DATASET_INGESTION.value, DatasetIngestionTask)


# Automatically register default tasks on package import
register_default_tasks()

__all__ = [
    "DocumentIngestionTask",
    "DatasetIngestionTask",
    "ChunkingTask",
    "EmbeddingTask",
    "VectorIndexingTask",
    "EvaluationTask",
    "ReportExportTask",
    "DataSourceSyncTask",
    "register_default_tasks",
]

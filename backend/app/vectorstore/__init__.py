"""Vector store subsystem for Enterprise AI Analyst."""

from app.vectorstore.collection import CollectionManager, build_collection_name
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.exceptions import (
    CollectionMismatchError,
    TenantIsolationError,
    VectorStoreConfigurationError,
    VectorStoreConnectionError,
    VectorStoreError,
    VectorStoreTimeoutError,
    VectorStoreValidationError,
)
from app.vectorstore.filters import TenantVectorFilterBuilder
from app.vectorstore.hashing import compute_vector_point_id
from app.vectorstore.health import VectorStoreHealthChecker
from app.vectorstore.models import IndexingBatchResult, VectorPoint, VectorStoreStats
from app.vectorstore.payload import PayloadBuilder
from app.vectorstore.providers import (
    FakeVectorStoreProvider,
    QdrantVectorStoreProvider,
    VectorStore,
)
from app.vectorstore.schemas import (
    DocumentIndexingResponse,
    DocumentIndexingStatusResponse,
    VectorStoreHealthResponse,
    VectorStoreStatsResponse,
)
from app.vectorstore.service import VectorStoreService

__all__ = [
    "VectorStoreConfig",
    "VectorStoreError",
    "VectorStoreConfigurationError",
    "VectorStoreConnectionError",
    "VectorStoreTimeoutError",
    "VectorStoreValidationError",
    "CollectionMismatchError",
    "TenantIsolationError",
    "VectorPoint",
    "VectorStoreStats",
    "IndexingBatchResult",
    "DocumentIndexingResponse",
    "DocumentIndexingStatusResponse",
    "VectorStoreStatsResponse",
    "VectorStoreHealthResponse",
    "PayloadBuilder",
    "CollectionManager",
    "build_collection_name",
    "TenantVectorFilterBuilder",
    "compute_vector_point_id",
    "VectorStoreHealthChecker",
    "VectorStore",
    "FakeVectorStoreProvider",
    "QdrantVectorStoreProvider",
    "VectorStoreService",
]

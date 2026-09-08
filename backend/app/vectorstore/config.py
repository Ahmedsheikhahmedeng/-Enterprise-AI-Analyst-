"""Vector store configuration models and resolution."""

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class VectorStoreConfig:
    """Immutable configuration for Qdrant vector store operations."""

    url: str = "http://localhost:6333"
    api_key: str | None = None
    timeout_seconds: float = 10.0
    collection_prefix: str = "enterprise_ai"
    distance: str = "cosine"
    vector_size: int | None = 1536
    upsert_batch_size: int = 100
    max_concurrent_requests: int = 5
    retry_count: int = 3
    retry_backoff: float = 0.5

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "VectorStoreConfig":
        s = settings or get_settings()
        return cls(
            url=s.QDRANT_URL.strip(),
            api_key=s.QDRANT_API_KEY,
            timeout_seconds=s.QDRANT_TIMEOUT_SECONDS,
            collection_prefix=s.QDRANT_COLLECTION_PREFIX.strip(),
            distance=s.QDRANT_DISTANCE.strip().lower(),
            vector_size=s.QDRANT_VECTOR_SIZE or s.EMBEDDING_DIMENSIONS,
            upsert_batch_size=s.QDRANT_UPSERT_BATCH_SIZE,
            max_concurrent_requests=s.QDRANT_MAX_CONCURRENT_REQUESTS,
            retry_count=s.QDRANT_RETRY_COUNT,
            retry_backoff=s.QDRANT_RETRY_BACKOFF,
        )

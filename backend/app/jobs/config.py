"""Configuration settings for Background Jobs and Distributed Workers."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class JobConfig(BaseSettings):
    """Configuration for jobs, queues, workers, retries and observability."""

    model_config = SettingsConfigDict(
        env_prefix="JOB_",
        env_file=".env",
        extra="ignore",
    )

    # Worker concurrency
    WORKER_CONCURRENCY: int = 4
    MAX_CONCURRENT_PER_TYPE: dict[str, int] = {
        "embedding": 4,
        "evaluation": 2,
        "report_export": 2,
        "document_ingestion": 4,
        "chunking": 4,
        "vector_indexing": 4,
    }

    # Payload & result constraints
    MAX_PAYLOAD_BYTES: int = 65536  # 64 KB
    MAX_RESULT_BYTES: int = 65536  # 64 KB

    # Queue & visibility semantics
    VISIBILITY_TIMEOUT_SECONDS: int = 300  # 5 minutes
    MAX_QUEUE_DEPTH: int = 10000
    MAX_IN_FLIGHT_JOBS: int = 1000

    # Retry policy defaults
    DEFAULT_MAX_ATTEMPTS: int = 3
    RETRY_INITIAL_DELAY_SECONDS: float = 1.0
    RETRY_MAX_DELAY_SECONDS: float = 60.0
    RETRY_BACKOFF_FACTOR: float = 2.0
    RETRY_JITTER: bool = True

    # Stuck job detection & Worker heartbeat
    WORKER_HEARTBEAT_INTERVAL_SECONDS: int = 15
    WORKER_HEARTBEAT_TTL_SECONDS: int = 45
    STUCK_JOB_TIMEOUT_SECONDS: int = 600  # 10 minutes

    # Shutdown
    WORKER_SHUTDOWN_TIMEOUT_SECONDS: int = 30

    # Retention
    RETENTION_DAYS: int = 30
    DEAD_LETTER_RETENTION_DAYS: int = 90


job_config = JobConfig()

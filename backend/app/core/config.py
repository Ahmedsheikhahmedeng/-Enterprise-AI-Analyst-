from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration managed via environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --------------------------------------------------------------------------
    # 1. APPLICATION
    # --------------------------------------------------------------------------
    APP_NAME: str = Field(
        default="Enterprise AI Analyst API",
        description="Public title of the service",
    )
    APP_VERSION: str = Field(
        default="0.1.0",
        description="Semantic version of the service",
    )
    ENVIRONMENT: Literal["development", "staging", "production", "testing"] = Field(
        default="development",
        description="Runtime deployment environment",
    )
    DEBUG: bool = Field(
        default=False,
        description="Debug mode toggle for verbose output",
    )
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Minimum structured logging level",
    )
    API_V1_PREFIX: str = Field(
        default="/api/v1",
        description="Prefix for v1 REST endpoints",
    )
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins list",
    )

    # --------------------------------------------------------------------------
    # 2. DATABASE (POSTGRESQL)
    # --------------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_ai_analyst",
        description="Asynchronous PostgreSQL connection URI via asyncpg",
    )
    DATABASE_POOL_SIZE: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of persistent connections in connection pool",
    )
    DATABASE_MAX_OVERFLOW: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum number of additional temporary overflow connections",
    )
    DATABASE_POOL_TIMEOUT: float = Field(
        default=30.0,
        ge=1.0,
        description="Seconds to wait before timing out on connection pool retrieval",
    )
    DATABASE_POOL_RECYCLE: int = Field(
        default=1800,
        ge=60,
        description="Seconds after which connections are recycled to prevent stale timeouts",
    )

    # --------------------------------------------------------------------------
    # 3. REDIS
    # --------------------------------------------------------------------------
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching, queues, and locks",
    )
    REDIS_CONNECT_TIMEOUT: float = Field(
        default=5.0,
        ge=0.5,
        description="Seconds to wait for Redis connection before timing out",
    )

    # --------------------------------------------------------------------------
    # 4. QDRANT
    # --------------------------------------------------------------------------
    QDRANT_URL: str = Field(
        default="http://localhost:6333",
        description="Qdrant vector engine HTTP/gRPC endpoint",
    )
    QDRANT_API_KEY: str | None = Field(
        default=None,
        description="Optional API key for authenticated Qdrant clusters",
    )
    QDRANT_TIMEOUT: int = Field(
        default=30,
        ge=1,
        description="Seconds before Qdrant API requests time out",
    )
    QDRANT_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        ge=1.0,
        description="Floating-point timeout in seconds for Qdrant API calls",
    )
    QDRANT_COLLECTION_PREFIX: str = Field(
        default="enterprise_ai",
        description="Prefix for deterministic vector store collection naming",
    )
    QDRANT_DISTANCE: str = Field(
        default="cosine",
        description="Distance metric for vector search (cosine, dot, euclidean)",
    )
    QDRANT_VECTOR_SIZE: int | None = Field(
        default=None,
        description="Optional explicit vector size override (defaults to EMBEDDING_DIMENSIONS)",
    )
    QDRANT_UPSERT_BATCH_SIZE: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Batch size for vector upsert operations",
    )
    QDRANT_MAX_CONCURRENT_REQUESTS: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum concurrent batch requests to Qdrant",
    )
    QDRANT_RETRY_COUNT: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts on transient Qdrant communication failures",
    )
    QDRANT_RETRY_BACKOFF: float = Field(
        default=1.5,
        ge=1.0,
        le=10.0,
        description="Exponential backoff factor for Qdrant transient retries",
    )

    # --------------------------------------------------------------------------
    # 5. INFRASTRUCTURE STARTUP RETRIES & INTEGRATION TESTING
    # --------------------------------------------------------------------------
    INFRASTRUCTURE_STARTUP_RETRIES: int = Field(
        default=3,
        ge=1,
        description="Number of startup connectivity retry attempts before proceeding",
    )
    INFRASTRUCTURE_RETRY_DELAY: float = Field(
        default=1.0,
        ge=0.1,
        description="Delay in seconds between startup retry attempts",
    )
    RUN_INTEGRATION_TESTS: bool = Field(
        default=False,
        description="Flag enabling tests that require real running Docker services",
    )

    # --------------------------------------------------------------------------
    # 6. AUTHENTICATION & JWT
    # --------------------------------------------------------------------------
    JWT_SECRET_KEY: str = Field(
        default="dev-insecure-jwt-secret-key-at-least-32-bytes-long-123456",
        description="Cryptographic secret key for signing JWT access tokens",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Cryptographic algorithm for JWT signatures",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=15,
        ge=1,
        description="Lifespan of JWT access tokens in minutes",
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        ge=1,
        description="Lifespan of refresh tokens in days",
    )
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60,
        ge=1,
        description="Lifespan of password reset tokens in minutes",
    )
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = Field(
        default=24,
        ge=1,
        description="Lifespan of email verification tokens in hours",
    )

    # --------------------------------------------------------------------------
    # 7. STORAGE
    # --------------------------------------------------------------------------
    STORAGE_BACKEND: Literal["local", "s3"] = Field(
        default="local",
        description="Active storage provider backend",
    )
    LOCAL_STORAGE_ROOT: str = Field(
        default="storage",
        description="Base filesystem root directory for local storage provider",
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=25,
        ge=1,
        le=500,
        description="Maximum permitted file upload size in megabytes",
    )
    S3_ENDPOINT_URL: str | None = Field(
        default=None,
        description="Optional custom S3 endpoint URL (for MinIO, Cloudflare R2, LocalStack)",
    )
    S3_BUCKET: str = Field(
        default="enterprise-documents",
        description="Target S3 bucket name for document persistence",
    )
    S3_REGION: str = Field(
        default="us-east-1",
        description="Target S3 region identifier",
    )
    S3_ACCESS_KEY_ID: str | None = Field(
        default=None,
        description="Optional S3 access key ID (required when STORAGE_BACKEND is s3)",
    )
    S3_SECRET_ACCESS_KEY: str | None = Field(
        default=None,
        description="Optional S3 secret access key (required when STORAGE_BACKEND is s3)",
    )

    # --------------------------------------------------------------------------
    # 8. DOCUMENT INGESTION & RESOURCE LIMITS
    # --------------------------------------------------------------------------
    MAX_INGESTION_PAGES: int = Field(
        default=500,
        ge=1,
        le=5000,
        description="Maximum permitted pages to parse per document",
    )
    MAX_INGESTION_ROWS: int = Field(
        default=50000,
        ge=1,
        le=500000,
        description="Maximum permitted rows to parse per tabular file (CSV/XLSX)",
    )
    MAX_INGESTION_SHEETS: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum permitted sheets to parse per Excel workbook",
    )
    MAX_EXTRACTED_CHARACTERS: int = Field(
        default=5_000_000,
        ge=1000,
        description="Maximum permitted total characters extracted from document",
    )
    AUTO_INGEST: bool = Field(
        default=True,
        description="Automatically enqueue asynchronous ingestion after document upload",
    )

    # --------------------------------------------------------------------------
    # 9. EMBEDDINGS & VECTOR GENERATION CONFIGURATION
    # --------------------------------------------------------------------------
    EMBEDDING_PROVIDER: str = Field(
        default="local",
        description="Active embedding provider: 'openai', 'local', or 'mock'",
    )
    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="Active embedding model name",
    )
    EMBEDDING_DIMENSIONS: int = Field(
        default=1536,
        ge=1,
        description="Expected embedding vector dimension",
    )
    EMBEDDING_BATCH_SIZE: int = Field(
        default=64,
        ge=1,
        le=2048,
        description="Batch size for vector generation",
    )
    EMBEDDING_MAX_INPUT_TOKENS: int = Field(
        default=8191,
        ge=1,
        description="Max input tokens allowed per single chunk",
    )
    EMBEDDING_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        gt=0,
        description="HTTP request timeout for provider calls in seconds",
    )
    EMBEDDING_MAX_RETRIES: int = Field(
        default=3,
        ge=0,
        description="Max retries with exponential backoff on transient errors",
    )
    EMBEDDING_RETRY_BACKOFF_FACTOR: float = Field(
        default=0.5,
        ge=0.0,
        description="Base factor for exponential backoff",
    )
    EMBEDDING_NORMALIZE: bool = Field(
        default=True,
        description="Whether to L2-normalize vectors",
    )
    EMBEDDING_CACHE_ENABLED: bool = Field(
        default=True,
        description="Enable embedding cache",
    )
    EMBEDDING_CACHE_TTL_SECONDS: int = Field(
        default=604800,  # 7 days
        ge=60,
        description="TTL for cached embeddings in seconds",
    )
    EMBEDDING_MAX_CONCURRENT_REQUESTS: int = Field(
        default=5,
        ge=1,
        description="Maximum concurrent in-flight embedding requests",
    )
    EMBEDDING_API_KEY: str | None = Field(
        default=None,
        description="API key for cloud embedding provider (e.g. OpenAI)",
    )
    EMBEDDING_API_BASE_URL: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for OpenAI-compatible embedding API",
    )
    EMBEDDING_VERSION: str = Field(
        default="1.0.0",
        description="Embedding pipeline configuration version",
    )

    # --------------------------------------------------------------------------
    # 11. DENSE RETRIEVAL
    # --------------------------------------------------------------------------
    RETRIEVAL_DEFAULT_TOP_K: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Default number of nearest chunks to retrieve",
    )
    RETRIEVAL_MAX_TOP_K: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Maximum permitted top_k requested by client",
    )
    RETRIEVAL_MIN_QUERY_CHARACTERS: int = Field(
        default=2,
        ge=1,
        description="Minimum permitted search query length in characters",
    )
    RETRIEVAL_MAX_QUERY_CHARACTERS: int = Field(
        default=1000,
        ge=10,
        le=10000,
        description="Maximum permitted search query length in characters",
    )
    RETRIEVAL_MAX_QUERY_TOKENS: int = Field(
        default=512,
        ge=1,
        le=8192,
        description="Maximum permitted query token count before rejection/truncation",
    )
    RETRIEVAL_SCORE_THRESHOLD: float | None = Field(
        default=None,
        description="Optional global default minimum score threshold for similarity search",
    )
    RETRIEVAL_PARENT_CONTEXT_ENABLED: bool = Field(
        default=True,
        description="Whether parent context resolution is enabled by default",
    )
    RETRIEVAL_TIMEOUT_SECONDS: float = Field(
        default=15.0,
        ge=1.0,
        le=60.0,
        description="Maximum timeout in seconds for vector retrieval execution",
    )

    # --------------------------------------------------------------------------
    # 12. HYBRID RETRIEVAL & BM25
    # --------------------------------------------------------------------------
    HYBRID_RETRIEVAL_ENABLED: bool = Field(
        default=True,
        description="Master switch to enable/disable hybrid retrieval API and workflows",
    )
    HYBRID_DEFAULT_TOP_K: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Default number of final merged chunks to return from hybrid retrieval",
    )
    HYBRID_MAX_TOP_K: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum permitted final top_k in hybrid retrieval requests",
    )
    HYBRID_DENSE_CANDIDATE_K: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Default candidate pool size retrieved from dense vector search",
    )
    HYBRID_SPARSE_CANDIDATE_K: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Default candidate pool size retrieved from sparse BM25 search",
    )
    HYBRID_RRF_K: int = Field(
        default=60,
        ge=1,
        le=200,
        description="Smoothing constant k for Reciprocal Rank Fusion formula: 1 / (k + rank)",
    )
    HYBRID_ALLOW_PARTIAL_FAILURE: bool = Field(
        default=True,
        description="Allow degraded response if either dense or sparse search fails",
    )
    BM25_K1: float = Field(
        default=1.2,
        ge=0.0,
        le=5.0,
        description="Okapi BM25 term frequency saturation parameter k1",
    )
    BM25_B: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Okapi BM25 document length normalization parameter b",
    )
    SPARSE_INDEX_VERSION: str = Field(
        default="bm25-v1",
        description="Deterministic version tag for sparse tokenizer and analyzer pipeline",
    )
    SPARSE_STRIP_ARABIC_DIACRITICS: bool = Field(
        default=True,
        description="Whether to strip Tashkeel (Arabic diacritics) during sparse tokenization",
    )

    # -------------------------------------------------------------------------
    # Cross-Encoder Reranker Settings (Task 14)
    # -------------------------------------------------------------------------
    RERANKING_ENABLED: bool = Field(
        default=True,
        description="Global feature flag for Cross-Encoder Reranking layer",
    )
    RERANKER_PROVIDER: str = Field(
        default="local",
        description="Reranker provider ('local', 'sentence-transformers')",
    )
    RERANKER_MODEL: str = Field(
        default="local-cross-encoder-v1",
        description="Cross-Encoder model identifier or local variant",
    )
    RERANKER_VERSION: str = Field(
        default="reranker-v1",
        description="Version tag for reranker scoring and provenance tracking",
    )
    RERANKER_DEVICE: str = Field(
        default="auto",
        description="Target compute device: 'auto', 'cpu', 'cuda', or 'mps'",
    )
    RERANKER_BATCH_SIZE: int = Field(
        default=16,
        ge=1,
        le=128,
        description="Batch size for cross-encoder pair scoring inference",
    )
    RERANKER_MAX_CANDIDATES: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum candidates passed to cross-encoder reranking",
    )
    RERANKER_FINAL_K: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Final top-K documents selected after cross-encoder reranking",
    )
    RERANKER_MAX_INPUT_TOKENS: int = Field(
        default=512,
        ge=64,
        le=4096,
        description="Max tokens per query-candidate pair before safety truncation",
    )
    RERANKER_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Max execution timeout for reranking inference in seconds",
    )
    RERANKER_MAX_CONCURRENT_BATCHES: int = Field(
        default=2,
        ge=1,
        le=16,
        description="Max concurrent batch scoring tasks executed in parallel",
    )
    RERANKER_ALLOW_FALLBACK: bool = Field(
        default=True,
        description="Whether to gracefully fallback to RRF rankings if reranker fails",
    )

    # --------------------------------------------------------------------------
    # 14. QUERY UNDERSTANDING, REWRITING & MULTI-QUERY RETRIEVAL
    # --------------------------------------------------------------------------
    QUERY_UNDERSTANDING_ENABLED: bool = Field(
        default=True,
        description="Global feature flag for Query Understanding & Planning pipeline",
    )
    QUERY_REWRITE_ENABLED: bool = Field(
        default=True,
        description="Whether to rewrite ambiguous queries into search-oriented forms",
    )
    QUERY_EXPANSION_ENABLED: bool = Field(
        default=True,
        description="Whether to generate domain synonyms and alternative query phrasings",
    )
    QUERY_DECOMPOSITION_ENABLED: bool = Field(
        default=True,
        description="Whether to decompose complex/comparative queries into sub-queries",
    )
    QUERY_DETERMINISTIC_MODE: bool = Field(
        default=False,
        description="Uses rule-based offline algorithms with zero external LLM dependencies",
    )
    QUERY_UNDERSTANDING_PROVIDER: str = Field(
        default="deterministic",
        description="Active provider for query understanding ('deterministic' or 'llm')",
    )
    QUERY_MAX_ALTERNATIVE_QUERIES: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum alternative/expanded queries generated per request",
    )
    QUERY_MAX_SUBQUERIES: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum decomposed sub-queries generated per request",
    )
    QUERY_MAX_TOTAL_QUERIES: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Hard ceiling on total queries planned and executed per retrieval request",
    )
    QUERY_UNDERSTANDING_TIMEOUT_SECONDS: float = Field(
        default=3.0,
        ge=0.1,
        le=30.0,
        description="Maximum timeout in seconds for query understanding and planning phase",
    )
    QUERY_TOTAL_PIPELINE_TIMEOUT_SECONDS: float = Field(
        default=15.0,
        ge=1.0,
        le=60.0,
        description="End-to-end timeout for query understanding and multi-query retrieval",
    )
    QUERY_LLM_MAX_TOKENS: int = Field(
        default=512,
        ge=64,
        le=2048,
        description="Maximum output tokens for LLM query understanding responses",
    )
    QUERY_ANALYSIS_CONFIDENCE_THRESHOLD: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold required to apply rewrites over original query",
    )
    QUERY_REWRITE_PROMPT_VERSION: str = Field(
        default="v1",
        description="Active version identifier for LLM rewrite prompts",
    )

    # --------------------------------------------------------------------------
    # 13. RAG & ANSWER GENERATION (TASK 16)
    # --------------------------------------------------------------------------
    RAG_ENABLED: bool = Field(
        default=True,
        description="Global feature flag toggling evidence-grounded RAG answer generation",
    )
    RAG_LLM_PROVIDER: str = Field(
        default="deterministic",
        description="Active LLM provider for RAG answer generation (deterministic, openai)",
    )
    RAG_LLM_MODEL: str = Field(
        default="gpt-4o-mini",
        description="Target model identifier for LLM generation",
    )
    RAG_LLM_API_KEY: str | None = Field(
        default=None,
        description="API key for external LLM generation provider",
    )
    RAG_LLM_BASE_URL: str | None = Field(
        default=None,
        description="Base URL for external LLM generation provider",
    )
    RAG_LLM_TEMPERATURE: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for grounded RAG answers",
    )
    RAG_MAX_OUTPUT_TOKENS: int = Field(
        default=1024,
        ge=64,
        le=4096,
        description="Maximum output tokens for generated RAG answers",
    )
    RAG_MAX_CONTEXT_TOKENS: int = Field(
        default=4000,
        ge=500,
        le=32000,
        description="Maximum token budget allocated for evidence context assembly",
    )
    RAG_EVIDENCE_TOP_K: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum evidence chunks to assemble into generation context",
    )
    RAG_MIN_EVIDENCE_SCORE: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum rerank/relevance score required to consider evidence",
    )
    RAG_LLM_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Timeout in seconds for LLM generation calls",
    )
    RAG_LLM_MAX_RETRIES: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum retry attempts on transient LLM generation errors",
    )
    RAG_PROMPT_VERSION: str = Field(
        default="v1",
        description="Active system prompt version for grounded RAG",
    )
    RAG_RESPONSE_LANGUAGE: str = Field(
        default="auto",
        description="Response language policy: 'auto', 'en', 'ar', 'tr'",
    )
    RAG_MAX_LLM_COST_PER_REQUEST: float = Field(
        default=0.10,
        ge=0.0,
        description="Upper safety ceiling in USD for a single RAG request",
    )

    # --------------------------------------------------------------------------
    # 16. SECURE SQL AGENT & STRUCTURED DATA ANALYSIS
    # --------------------------------------------------------------------------
    SQL_AGENT_ENABLED: bool = Field(
        default=True,
        description="Global feature flag for Secure SQL Agent pipeline",
    )
    SQL_LLM_PROVIDER: str = Field(
        default="deterministic",
        description="Active provider for SQL generation: 'deterministic' or 'openai'",
    )
    SQL_LLM_MODEL: str = Field(
        default="gpt-4o-mini",
        description="Active model name for SQL generation",
    )
    SQL_LLM_API_KEY: str | None = Field(
        default=None,
        description="API key for external SQL generation provider",
    )
    SQL_LLM_BASE_URL: str | None = Field(
        default=None,
        description="Base URL for external SQL generation provider",
    )
    SQL_STATEMENT_TIMEOUT_MS: int = Field(
        default=5000,
        ge=100,
        le=60000,
        description="Database statement-level timeout in milliseconds",
    )
    SQL_QUERY_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        ge=1.0,
        le=120.0,
        description="Application-level execution timeout in seconds",
    )
    SQL_MAX_ROWS: int = Field(
        default=5000,
        ge=1,
        le=50000,
        description="Maximum rows returned by a single SQL agent query execution",
    )
    SQL_MAX_RESULT_BYTES: int = Field(
        default=5_000_000,
        ge=1000,
        description="Maximum byte size permitted for serialized query results",
    )
    SQL_MAX_JOINS: int = Field(
        default=5,
        ge=0,
        le=15,
        description="Maximum allowed JOIN operations in an analyzed SQL statement",
    )
    SQL_MAX_CTES: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum allowed CTEs in an analyzed SQL statement",
    )
    SQL_MAX_SUBQUERY_DEPTH: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum allowed nested subquery depth",
    )
    SQL_SCHEMA_CACHE_TTL_SECONDS: int = Field(
        default=300,
        ge=0,
        le=86400,
        description="Time-to-live in seconds for cached tenant table schema definitions",
    )
    SQL_PROMPT_VERSION: str = Field(
        default="sql-v1.0",
        description="Active prompt version for SQL generation",
    )
    SQL_MAX_LLM_COST_PER_REQUEST: float = Field(
        default=0.10,
        ge=0.0,
        description="Maximum allowable LLM cost in USD per SQL generation request",
    )

    # --------------------------------------------------------------------------
    # 17. UNIFIED AI ANALYST ORCHESTRATOR CONFIGURATION
    # --------------------------------------------------------------------------
    ANALYST_ENABLED: bool = Field(
        default=True,
        description="Master toggle enabling unified AI analyst orchestrator",
    )
    ANALYST_PLANNER_PROVIDER: str = Field(
        default="deterministic",
        description="Analyst planner provider: 'deterministic' or 'llm'",
    )
    ANALYST_TOTAL_TIMEOUT_SECONDS: float = Field(
        default=25.0,
        ge=2.0,
        le=120.0,
        description="Maximum shared deadline in seconds for entire unified analyst request",
    )
    ANALYST_SQL_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Branch timeout for SQL agent execution",
    )
    ANALYST_RAG_TIMEOUT_SECONDS: float = Field(
        default=15.0,
        ge=1.0,
        le=60.0,
        description="Branch timeout for RAG execution",
    )
    ANALYST_MAX_BRANCHES: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Maximum concurrent branches in an execution plan",
    )
    ANALYST_MAX_TOTAL_QUERIES: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Maximum subqueries dispatched across all branches",
    )
    ANALYST_MAX_EVIDENCE: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum consolidated evidence items sent to final generation",
    )
    ANALYST_MAX_CONTEXT_TOKENS: int = Field(
        default=6000,
        ge=500,
        le=32000,
        description="Maximum context tokens budget for unified final prompt",
    )
    ANALYST_PROMPT_VERSION: str = Field(
        default="analyst-v1.0",
        description="Prompt version for unified answer generation",
    )

    @property
    def max_upload_size_bytes(self) -> int:
        """Return maximum permitted upload size converted to bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, v: str, info: ValidationInfo) -> str:
        env = info.data.get("ENVIRONMENT", "development")
        if env == "production" and (not v or v.startswith("dev-insecure") or len(v) < 32):
            raise ValueError(
                "In production, JWT_SECRET_KEY must be an explicitly configured secret "
                "with at least 32 characters."
            )
        return v

    @field_validator("S3_ACCESS_KEY_ID")
    @classmethod
    def validate_s3_access_key(cls, v: str | None, info: ValidationInfo) -> str | None:
        backend = info.data.get("STORAGE_BACKEND", "local")
        if backend == "s3" and not v:
            raise ValueError("S3_ACCESS_KEY_ID is required when STORAGE_BACKEND is 's3'")
        return v

    @field_validator("S3_SECRET_ACCESS_KEY")
    @classmethod
    def validate_s3_secret_key(cls, v: str | None, info: ValidationInfo) -> str | None:
        backend = info.data.get("STORAGE_BACKEND", "local")
        if backend == "s3" and not v:
            raise ValueError("S3_SECRET_ACCESS_KEY is required when STORAGE_BACKEND is 's3'")
        return v

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        """Enforce non-negotiable security requirements when running in production."""
        if self.ENVIRONMENT == "production":
            # 1. Debug mode must never be active in production
            if self.DEBUG:
                raise ValueError(
                    "Security violation: DEBUG mode must be disabled (False) in production."
                )

            # 2. Wildcard CORS origins are forbidden
            if "*" in self.CORS_ORIGINS:
                raise ValueError(
                    "Security violation: Wildcard CORS ('*') is prohibited in production when credentials are enabled."
                )

            # 3. Secret keys must be explicitly configured and strong
            if (
                not self.JWT_SECRET_KEY
                or self.JWT_SECRET_KEY.startswith("dev-insecure")
                or self.JWT_SECRET_KEY.startswith("change-me")
                or len(self.JWT_SECRET_KEY) < 32
            ):
                raise ValueError(
                    "Security violation: In production, JWT_SECRET_KEY must be an explicit, non-default secret "
                    "with at least 32 characters."
                )

            # 4. Backing databases must not use default local development credentials
            if "postgres:postgres@localhost" in self.DATABASE_URL:
                raise ValueError(
                    "Security violation: In production, DATABASE_URL must not point to default local credentials."
                )

            if not self.DATABASE_URL or not self.REDIS_URL or not self.QDRANT_URL:
                raise ValueError(
                    "Security violation: In production, DATABASE_URL, REDIS_URL, and QDRANT_URL must all be set."
                )

        return self

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == "testing"

    @property
    def sanitized_database_url(self) -> str:
        """Return DATABASE_URL with credentials redacted for safe logging."""
        try:
            parts = urlsplit(self.DATABASE_URL)
            if parts.password:
                netloc = f"{parts.username}:***@{parts.hostname}"
                if parts.port:
                    netloc += f":{parts.port}"
                return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
            return self.DATABASE_URL
        except Exception:
            return "postgresql+asyncpg://[REDACTED]"

    @property
    def sanitized_redis_url(self) -> str:
        """Return REDIS_URL with credentials redacted for safe logging."""
        try:
            parts = urlsplit(self.REDIS_URL)
            if parts.password:
                netloc = f":***@{parts.hostname}"
                if parts.port:
                    netloc += f":{parts.port}"
                return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
            return self.REDIS_URL
        except Exception:
            return "redis://[REDACTED]"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton instance of application settings."""
    return Settings()

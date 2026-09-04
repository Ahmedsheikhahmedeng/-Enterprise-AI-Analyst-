from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, field_validator
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
        default=5,
        ge=1,
        description="Seconds before Qdrant API requests time out",
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

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

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

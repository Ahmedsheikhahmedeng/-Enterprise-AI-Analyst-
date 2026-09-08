"""Configuration settings and operational thresholds for Enterprise Agent Memory."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MemoryConfig(BaseSettings):
    """Runtime configuration, TTLs, and limits for memory storage and retrieval."""

    model_config = SettingsConfigDict(
        env_prefix="MEMORY_",
        case_sensitive=False,
        extra="ignore",
    )

    # Retention TTLs (seconds)
    short_term_ttl_seconds: int = Field(
        default=3600, ge=60, description="1 hour TTL for short-term memory"
    )
    working_memory_ttl_seconds: int = Field(
        default=86400, ge=300, description="24 hours TTL for working memory"
    )
    episodic_memory_ttl_seconds: int = Field(
        default=2592000, ge=3600, description="30 days TTL for episodic memory"
    )
    semantic_memory_ttl_seconds: int | None = Field(
        default=None, description="None = infinite retention for semantic memory"
    )

    # Hard Capacity Limits
    max_memories_per_user: int = Field(default=1000, ge=10, le=100000)
    max_memories_per_org: int = Field(default=50000, ge=100, le=1000000)
    max_memory_size_bytes: int = Field(
        default=32768, ge=256, le=1048576, description="32KB per item"
    )
    max_memory_context_tokens: int = Field(default=2048, ge=100, le=32000)
    max_memory_search_k: int = Field(default=10, ge=1, le=100)

    # Scoring & Deduplication Thresholds
    default_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    default_importance_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    similarity_dedup_threshold: float = Field(default=0.92, ge=0.5, le=1.0)
    recency_half_life_days: float = Field(default=30.0, ge=1.0)

    # Vector Storage
    qdrant_collection_name: str = Field(default="agent_memories")
    vector_search_enabled: bool = Field(default=True)


@lru_cache(maxsize=1)
def get_memory_config() -> MemoryConfig:
    """Return cached singleton MemoryConfig instance."""
    return MemoryConfig()

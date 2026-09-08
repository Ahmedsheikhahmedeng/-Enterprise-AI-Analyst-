"""Retention policy calculating expirations and filtering expired memory items."""

from datetime import UTC, datetime, timedelta

from app.memory.config import MemoryConfig, get_memory_config
from app.memory.schemas import MemoryType


class MemoryRetentionPolicy:
    """Manages TTL assignment and expiration validation across memory tiers."""

    def __init__(self, config: MemoryConfig | None = None) -> None:
        self.config = config or get_memory_config()

    def compute_expiration(
        self,
        memory_type: MemoryType,
        base_time: datetime | None = None,
    ) -> datetime | None:
        """Calculate expires_at timestamp based on memory tier TTL."""
        now = base_time or datetime.now(UTC)

        if memory_type == MemoryType.SHORT_TERM:
            return now + timedelta(seconds=self.config.short_term_ttl_seconds)
        if memory_type == MemoryType.WORKING:
            return now + timedelta(seconds=self.config.working_memory_ttl_seconds)
        if memory_type == MemoryType.EPISODIC:
            return now + timedelta(seconds=self.config.episodic_memory_ttl_seconds)
        if (
            memory_type == MemoryType.SEMANTIC
            and self.config.semantic_memory_ttl_seconds is not None
        ):
            return now + timedelta(seconds=self.config.semantic_memory_ttl_seconds)
        return None

    @staticmethod
    def is_expired(expires_at: datetime | None, check_time: datetime | None = None) -> bool:
        """Return True if expiration timestamp is non-null and in the past."""
        if expires_at is None:
            return False
        now = check_time or datetime.now(UTC)
        return expires_at <= now

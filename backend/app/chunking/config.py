"""Chunking subsystem configuration and limits.

Centralized constants controlling chunk size boundaries, token targets,
overlap parameters, and chunker versioning.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingConfig:
    """Immutable chunking configuration."""

    CHUNKER_VERSION: str = "1.0.0"

    # Token limits
    MIN_CHUNK_TOKENS: int = 50
    TARGET_CHUNK_TOKENS: int = 400
    MAX_CHUNK_TOKENS: int = 800  # Hard upper limit
    MAX_CHUNK_CHARACTERS: int = 4000  # Hard upper character limit

    # Overlap parameters
    OVERLAP_TOKENS: int = 60
    MAX_OVERLAP_FRACTION: float = 0.25

    # Parent chunk sizing
    MAX_PARENT_TOKENS: int = 1600

    # Small fragment merging threshold
    SMALL_CHUNK_THRESHOLD_TOKENS: int = 40

    # Table chunking: max rows per table slice if table exceeds token limit
    MAX_TABLE_ROWS_PER_SLICE: int = 30


# Default global instance
default_chunking_config = ChunkingConfig()

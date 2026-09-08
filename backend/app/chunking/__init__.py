"""Document chunking subsystem.

Provides structure-aware, deterministic, and multilingual semantic chunking
for canonical parsed documents.
"""

from app.chunking.config import ChunkingConfig, default_chunking_config
from app.chunking.exceptions import (
    ChunkingError,
    ChunkingLimitError,
    ChunkingPersistenceError,
    ChunkingValidationError,
)
from app.chunking.hashing import (
    compute_content_hash,
    generate_deterministic_chunk_id,
    normalize_chunk_text,
)
from app.chunking.models import (
    ChunkQualitySummary,
    ChunkType,
    IntermediateChunk,
    SourceLocator,
)
from app.chunking.service import ChunkingService, default_chunking_service
from app.chunking.tokenizer import (
    MultilingualTokenCounter,
    TokenCounter,
    default_token_counter,
)
from app.chunking.validators import validate_chunks

__all__ = [
    "ChunkQualitySummary",
    "ChunkType",
    "ChunkingConfig",
    "ChunkingError",
    "ChunkingLimitError",
    "ChunkingPersistenceError",
    "ChunkingService",
    "ChunkingValidationError",
    "IntermediateChunk",
    "MultilingualTokenCounter",
    "SourceLocator",
    "TokenCounter",
    "compute_content_hash",
    "default_chunking_config",
    "default_chunking_service",
    "default_token_counter",
    "generate_deterministic_chunk_id",
    "normalize_chunk_text",
    "validate_chunks",
]

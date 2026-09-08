"""Deterministic hashing and ID generation for document chunks."""

import hashlib
import re
import unicodedata
import uuid


def normalize_chunk_text(text: str) -> str:
    """Normalize text for consistent hashing and deduplication.

    Applies Unicode NFKC normalization, collapses consecutive whitespace,
    and strips leading/trailing space.
    """
    if not text:
        return ""
    # Unicode NFKC
    nfkc = unicodedata.normalize("NFKC", text)
    # Collapse multiple whitespace
    collapsed = re.sub(r"\s+", " ", nfkc)
    return collapsed.strip()


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of normalized chunk text.

    Returns a 64-character lowercase hexadecimal string.
    """
    normalized = normalize_chunk_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_deterministic_chunk_id(
    document_id: uuid.UUID,
    chunk_index: int,
    chunker_version: str,
    content_hash: str,
) -> uuid.UUID:
    """Generate a deterministic UUIDv5 for a chunk.

    Guarantees reproducibility: identical document, index, version, and content hash
    always produce the exact same UUID.
    """
    seed = f"{document_id}:{chunk_index}:{chunker_version}:{content_hash}"
    return uuid.uuid5(uuid.NAMESPACE_DNS, seed)

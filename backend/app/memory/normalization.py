"""Text normalization and content hashing utilities for Enterprise Agent Memory."""

import hashlib
import re


def normalize_memory_text(text: str) -> str:
    """Normalize text by collapsing whitespace, stripping control chars, and trimming."""
    if not text:
        return ""
    # Collapse consecutive whitespace to single space
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned


def compute_content_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash of normalized content."""
    normalized = normalize_memory_text(text).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

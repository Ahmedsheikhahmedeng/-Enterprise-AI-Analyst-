"""Deterministic Point ID hashing utilities for vector stores."""

import uuid

# Canonical namespace for enterprise vector point IDs
_VECTOR_POINT_NAMESPACE = uuid.UUID("a7b8c9d0-1234-5678-9abc-def012345678")


def compute_vector_point_id(
    organization_id: uuid.UUID,
    chunk_id: uuid.UUID,
    embedding_input_hash: str,
) -> uuid.UUID:
    """Compute a deterministic, collision-free UUIDv5 Point ID for Qdrant.

    Guarantees:
    - Identical chunk under identical embedding config yields the same Point ID.
    - Idempotent upserts replace points without duplicating records.
    - Fully compatible with Qdrant's native UUID point identifier format.
    """

    canonical_repr = (
        f"urn:vectorpoint:{organization_id}:{chunk_id}:{embedding_input_hash.strip().lower()}"
    )
    return uuid.uuid5(_VECTOR_POINT_NAMESPACE, canonical_repr)

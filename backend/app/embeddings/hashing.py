"""Deterministic embedding identity and cryptographic hashing."""

import hashlib


def compute_embedding_input_hash(
    normalized_text: str,
    provider: str,
    model: str,
    version: str,
    dimensions: int,
    normalization_mode: str,
) -> str:
    """Compute a deterministic SHA-256 fingerprint for an embedding request.

    Incorporates the normalized input text alongside all model configuration parameters
    that impact the resulting vector representation.
    """
    canonical_repr = (
        f"provider={provider.lower().strip()}|"
        f"model={model.lower().strip()}|"
        f"version={version.strip()}|"
        f"dimensions={dimensions}|"
        f"norm={normalization_mode.lower().strip()}|"
        f"text={normalized_text}"
    )
    return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

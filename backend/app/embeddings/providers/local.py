"""Deterministic local embedding provider for testing and offline development."""

import hashlib
import struct
from collections.abc import Sequence

from app.embeddings.models import EmbeddingVector
from app.embeddings.normalization import l2_normalize_vector
from app.embeddings.providers.base import ProviderEmbeddingResponse


class LocalDeterministicEmbeddingProvider:
    """Generates deterministic, high-quality normalized unit vectors locally.

    Uses SHA-256 digests seeded by text and dimension index to generate pseudo-random
    gaussian-distributed vectors that are strictly reproducible, fast, and offline.
    """

    def __init__(
        self,
        model_name: str = "local-deterministic-v1",
        dimensions: int = 1536,
    ) -> None:
        self._model_name = model_name
        self._dimensions = dimensions

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _generate_vector(self, text: str) -> EmbeddingVector:
        """Generate a deterministic unit vector for a single text."""
        vector: list[float] = []
        raw_seed = text.encode("utf-8")

        # We generate 4 bytes per float from consecutive hash slices
        step = 0
        while len(vector) < self._dimensions:
            h = hashlib.sha256(raw_seed + step.to_bytes(4, "big")).digest()
            for offset in range(0, len(h), 4):
                if len(vector) >= self._dimensions:
                    break
                chunk_bytes = h[offset : offset + 4]
                # Unpack as signed 32-bit int, then normalize to [-1.0, 1.0]
                int_val = struct.unpack(">i", chunk_bytes)[0]
                float_val = int_val / 2147483648.0
                vector.append(float_val)
            step += 1

        # L2 normalize the generated vector
        return l2_normalize_vector(vector)

    async def embed_texts(
        self,
        texts: Sequence[str],
    ) -> ProviderEmbeddingResponse:
        """Embed a sequence of texts deterministically while preserving order."""
        vectors = [self._generate_vector(t) for t in texts]
        # Approximate 1 token per 4 chars for synthetic metrics
        est_tokens = sum(max(1, len(t) // 4) for t in texts)
        return ProviderEmbeddingResponse(
            vectors=vectors,
            prompt_tokens=est_tokens,
            total_tokens=est_tokens,
            metadata={"provider": "local", "model": self._model_name},
        )

    async def health_check(self) -> bool:
        return True

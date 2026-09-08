"""SentenceTransformers cross-encoder provider using deep neural models."""

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from app.reranking.exceptions import (
    RerankerInferenceError,
    RerankerModelLoadError,
)

logger = logging.getLogger(__name__)


class SentenceTransformersRerankerProvider:
    """Wrapper around sentence-transformers CrossEncoder for GPU/CPU neural reranking."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        version: str = "reranker-v1",
        device: str = "auto",
        max_length: int = 512,
    ) -> None:
        self._model_name = model_name
        self._version = version
        self._requested_device = device
        self._max_length = max_length
        self._device = self._resolve_device(device)
        self._model: Any = None
        self._load_model()

    @property
    def provider_name(self) -> str:
        return "sentence-transformers"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def version(self) -> str:
        return self._version

    @property
    def device(self) -> str:
        return self._device

    def _resolve_device(self, requested: str) -> str:
        """Resolve device to 'cuda', 'mps', or 'cpu'."""
        req = requested.lower().strip()
        if req in ("cpu", "cuda", "mps"):
            return req

        # Auto detection
        try:
            import torch  # type: ignore[import-not-found]

            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass

        return "cpu"

    def _load_model(self) -> None:
        """Load CrossEncoder model instance."""
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-not-found]

            logger.info(
                "Loading CrossEncoder model '%s' on device '%s'...",
                self._model_name,
                self._device,
            )
            self._model = CrossEncoder(
                model_name=self._model_name,
                max_length=self._max_length,
                device=self._device,
            )
        except ImportError as exc:
            raise RerankerModelLoadError(
                "The 'sentence-transformers' package is not installed. "
                "Install it via 'pip install sentence-transformers' or use provider='local'."
            ) from exc
        except Exception as exc:
            raise RerankerModelLoadError(
                f"Failed to load CrossEncoder model '{self._model_name}': {exc}"
            ) from exc

    def _predict_sync(self, pairs_list: list[list[str]]) -> list[float]:
        """Synchronously execute CrossEncoder predict on pairs."""
        try:
            raw_scores = self._model.predict(pairs_list)
            # Normalize outputs to standard float list
            raw_list = raw_scores.tolist() if hasattr(raw_scores, "tolist") else list(raw_scores)
            return [float(s) for s in raw_list]
        except Exception as exc:
            raise RerankerInferenceError(f"Neural CrossEncoder inference failed: {exc}") from exc

    async def score_pairs(
        self,
        pairs: Sequence[tuple[str, str]],
    ) -> list[float]:
        """Asynchronously compute cross-encoder relevance scores in a worker thread."""
        if not pairs:
            return []

        pairs_list = [[q, t] for q, t in pairs]
        return await asyncio.to_thread(self._predict_sync, pairs_list)

    async def health_check(self) -> bool:
        return self._model is not None

"""Core EmbeddingService orchestrating normalization, caching, batching, and validation."""

import logging
import time
from collections.abc import Sequence
from typing import Any

from app.embeddings.batching import create_batches, process_batches_with_concurrency
from app.embeddings.cache import EmbeddingCache, NoopEmbeddingCache, build_embedding_cache_key
from app.embeddings.config import EmbeddingConfig
from app.embeddings.hashing import compute_embedding_input_hash
from app.embeddings.models import (
    EmbeddingBatchResult,
    EmbeddingItem,
    EmbeddingUsageMetrics,
    EmbeddingVector,
)
from app.embeddings.normalization import l2_normalize_vector
from app.embeddings.pricing import EmbeddingPricing
from app.embeddings.providers.base import EmbeddingProvider
from app.embeddings.text_builder import EmbeddingTextBuilder
from app.embeddings.tokenizer import EmbeddingTokenizer, UniversalEmbeddingTokenizer
from app.embeddings.validators import validate_embedding_vector

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Enterprise embedding service orchestrator.

    Completely decoupled from concrete provider SDKs. Coordinates text preparation,
    token counting, caching, concurrency-throttled batching, numeric validation,
    and cost/latency observability.
    """

    def __init__(
        self,
        config: EmbeddingConfig,
        provider: EmbeddingProvider,
        cache: EmbeddingCache | None = None,
        tokenizer: EmbeddingTokenizer | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.cache = cache or NoopEmbeddingCache()
        self.tokenizer = tokenizer or UniversalEmbeddingTokenizer(model_name=config.model)

    @property
    def provider_name(self) -> str:
        return self.provider.provider_name

    @property
    def model_name(self) -> str:
        return self.config.model

    @property
    def dimensions(self) -> int:
        return self.config.dimensions

    @property
    def version(self) -> str:
        return self.config.version

    async def embed_chunks(self, chunks: Sequence[Any]) -> EmbeddingBatchResult:
        """Embed a sequence of DocumentChunk objects while keeping original content immutable."""
        if not chunks:
            return EmbeddingBatchResult(
                items=[],
                metrics=EmbeddingUsageMetrics(
                    provider=self.provider.provider_name,
                    model=self.config.model,
                    version=self.config.version,
                    dimensions=self.config.dimensions,
                    batch_size=self.config.batch_size,
                    input_count=0,
                    total_input_tokens=0,
                ),
                status="success",
                failed_count=0,
                success_count=0,
            )

        items: list[EmbeddingItem] = []
        for chunk in chunks:
            chunk_id = getattr(chunk, "id", None)
            if chunk_id is None and isinstance(chunk, dict):
                chunk_id = chunk.get("id")

            try:
                prepared_text = EmbeddingTextBuilder.build_from_chunk(chunk)
                token_count = self.tokenizer.validate_limit(
                    prepared_text, self.config.max_input_tokens
                )
                norm_mode = "l2" if self.config.normalize else "none"
                inp_hash = compute_embedding_input_hash(
                    normalized_text=prepared_text,
                    provider=self.provider.provider_name,
                    model=self.config.model,
                    version=self.config.version,
                    dimensions=self.config.dimensions,
                    normalization_mode=norm_mode,
                )
                items.append(
                    EmbeddingItem(
                        chunk_id=chunk_id,
                        text=prepared_text,
                        embedding_input_hash=inp_hash,
                        token_count=token_count,
                    )
                )
            except Exception as exc:
                logger.error(f"Failed to prepare chunk {chunk_id} for embedding: {exc}")
                items.append(
                    EmbeddingItem(
                        chunk_id=chunk_id,
                        text="",
                        embedding_input_hash="",
                        token_count=0,
                        error=str(exc),
                    )
                )

        return await self._process_items(items)

    async def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatchResult:
        """Embed a sequence of raw strings."""
        if not texts:
            return EmbeddingBatchResult(
                items=[],
                metrics=EmbeddingUsageMetrics(
                    provider=self.provider.provider_name,
                    model=self.config.model,
                    version=self.config.version,
                    dimensions=self.config.dimensions,
                    batch_size=self.config.batch_size,
                    input_count=0,
                    total_input_tokens=0,
                ),
                status="success",
                failed_count=0,
                success_count=0,
            )

        items: list[EmbeddingItem] = []
        norm_mode = "l2" if self.config.normalize else "none"
        for text in texts:
            try:
                prepared_text = EmbeddingTextBuilder.build(text)
                token_count = self.tokenizer.validate_limit(
                    prepared_text, self.config.max_input_tokens
                )
                inp_hash = compute_embedding_input_hash(
                    normalized_text=prepared_text,
                    provider=self.provider.provider_name,
                    model=self.config.model,
                    version=self.config.version,
                    dimensions=self.config.dimensions,
                    normalization_mode=norm_mode,
                )
                items.append(
                    EmbeddingItem(
                        text=prepared_text,
                        embedding_input_hash=inp_hash,
                        token_count=token_count,
                    )
                )
            except Exception as exc:
                items.append(
                    EmbeddingItem(
                        text="",
                        embedding_input_hash="",
                        token_count=0,
                        error=str(exc),
                    )
                )

        return await self._process_items(items)

    async def _process_items(self, items: list[EmbeddingItem]) -> EmbeddingBatchResult:
        start_time = time.perf_counter()
        cache_hits = 0
        cache_misses = 0

        # 1. Cache Check (if enabled)
        items_to_embed_indices: list[int] = []
        if self.config.cache_enabled:
            keys: list[str] = []
            valid_indices: list[int] = []
            for idx, it in enumerate(items):
                if it.error is None and it.embedding_input_hash:
                    k = build_embedding_cache_key(
                        provider=self.provider.provider_name,
                        model=self.config.model,
                        version=self.config.version,
                        input_hash=it.embedding_input_hash,
                    )
                    keys.append(k)
                    valid_indices.append(idx)

            if keys:
                cached_vectors = await self.cache.get_many(keys)
                for v_idx, cached_vec in zip(valid_indices, cached_vectors, strict=True):
                    if cached_vec is not None:
                        try:
                            validate_embedding_vector(cached_vec, self.config.dimensions)
                            items[v_idx].vector = cached_vec
                            items[v_idx].cached = True
                            cache_hits += 1
                        except Exception:
                            # If cached vector is malformed, treat as cache miss
                            items_to_embed_indices.append(v_idx)
                            cache_misses += 1
                    else:
                        items_to_embed_indices.append(v_idx)
                        cache_misses += 1
        else:
            for idx, it in enumerate(items):
                if it.error is None:
                    items_to_embed_indices.append(idx)

        # 2. Batch Execution for Uncached Items
        provider_retries = 0
        if items_to_embed_indices:
            batches = create_batches(items_to_embed_indices, self.config.batch_size)

            async def _process_batch(
                batch_number: int, batch_indices: list[int]
            ) -> list[tuple[int, EmbeddingVector | None, str | None]]:
                batch_texts = [items[i].text for i in batch_indices]
                try:
                    resp = await self.provider.embed_texts(batch_texts)
                    batch_out: list[tuple[int, EmbeddingVector | None, str | None]] = []

                    if len(resp.vectors) != len(batch_indices):
                        err_msg = (
                            f"Provider output length mismatch: expected {len(batch_indices)}, "
                            f"got {len(resp.vectors)}"
                        )
                        return [(idx, None, err_msg) for idx in batch_indices]

                    for idx, vec in zip(batch_indices, resp.vectors, strict=True):
                        try:
                            validate_embedding_vector(vec, self.config.dimensions)
                            if self.config.normalize:
                                vec = l2_normalize_vector(vec)

                            batch_out.append((idx, vec, None))
                        except Exception as val_exc:
                            batch_out.append((idx, None, str(val_exc)))

                    return batch_out

                except Exception as exc:
                    logger.error(f"Provider error on batch {batch_number}: {exc}")
                    return [(idx, None, str(exc)) for idx in batch_indices]

            results = await process_batches_with_concurrency(
                batches=batches,
                process_fn=_process_batch,
                max_concurrency=self.config.max_concurrent_requests,
            )

            # Populate vectors & save newly computed embeddings to cache
            cache_to_set: list[tuple[str, list[float]]] = []
            for item_idx, vec, err in results:
                if vec is not None:
                    items[item_idx].vector = vec
                    if self.config.cache_enabled:
                        cache_key = build_embedding_cache_key(
                            provider=self.provider.provider_name,
                            model=self.config.model,
                            version=self.config.version,
                            input_hash=items[item_idx].embedding_input_hash,
                        )
                        cache_to_set.append((cache_key, vec))
                else:
                    items[item_idx].error = err

            if cache_to_set and self.config.cache_enabled:
                await self.cache.set_many(cache_to_set, ttl_seconds=self.config.cache_ttl_seconds)

        # 3. Aggregation & Metrics
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        success_count = sum(1 for it in items if it.is_success)
        failed_count = len(items) - success_count
        total_tokens = sum(it.token_count for it in items)

        if failed_count == 0:
            status = "success"
        elif success_count == 0:
            status = "failure"
        else:
            status = "partial"

        estimated_cost = EmbeddingPricing.estimate_cost(
            model=self.config.model,
            total_tokens=total_tokens,
            provider=self.provider.provider_name,
        )

        metrics = EmbeddingUsageMetrics(
            provider=self.provider.provider_name,
            model=self.config.model,
            version=self.config.version,
            dimensions=self.config.dimensions,
            batch_size=self.config.batch_size,
            input_count=len(items),
            total_input_tokens=total_tokens,
            latency_ms=latency_ms,
            retry_count=provider_retries,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            estimated_cost=estimated_cost,
        )

        return EmbeddingBatchResult(
            items=items,
            metrics=metrics,
            status=status,
            failed_count=failed_count,
            success_count=success_count,
        )

    async def embed_query(self, query: str) -> list[float]:
        """Generate normalized dense embedding for a natural language search query.

        Reuses active provider, tokenizer, normalization rules, and caching layer
        without invoking document chunking pipeline overhead.
        """
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Query string cannot be empty or whitespace-only.")

        self.tokenizer.validate_limit(clean_query, self.config.max_input_tokens)

        norm_mode = "l2" if self.config.normalize else "none"
        input_hash = compute_embedding_input_hash(
            normalized_text=clean_query,
            provider=self.provider.provider_name,
            model=self.config.model,
            version=self.config.version,
            dimensions=self.config.dimensions,
            normalization_mode=norm_mode,
        )
        cache_key = build_embedding_cache_key(
            provider=self.provider.provider_name,
            model=self.config.model,
            version=self.config.version,
            input_hash=input_hash,
        )

        if self.config.cache_enabled:
            cached_vec = await self.cache.get(cache_key)
            if cached_vec is not None:
                return cached_vec

        resp = await self.provider.embed_texts([clean_query])
        if not resp.vectors or not resp.vectors[0]:
            raise RuntimeError(
                f"Embedding provider '{self.provider.provider_name}' "
                "produced an empty vector for query."
            )

        vec = resp.vectors[0]
        if self.config.normalize:
            vec = l2_normalize_vector(vec)

        validate_embedding_vector(vec, expected_dimensions=self.config.dimensions)

        if self.config.cache_enabled:
            await self.cache.set(cache_key, vec, ttl_seconds=self.config.cache_ttl_seconds)

        return vec

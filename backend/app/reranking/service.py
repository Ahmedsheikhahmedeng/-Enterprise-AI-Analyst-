"""Domain service orchestrating cross-encoder candidate reranking and provenance tracking."""

import asyncio
import logging
import time
from uuid import UUID

from app.reranking.batching import create_batches
from app.reranking.config import RerankerConfig, get_reranker_config
from app.reranking.exceptions import (
    RerankerTimeoutError,
    RerankingError,
)
from app.reranking.models import (
    RerankedCandidate,
    RerankingDiagnostics,
    RerankingLatency,
    RerankingResult,
)
from app.reranking.providers.base import RerankerProvider
from app.reranking.providers.factory import RerankerProviderFactory
from app.reranking.validators import RerankerValidator
from app.retrieval.hybrid.models import FusedCandidate

logger = logging.getLogger(__name__)


class CrossEncoderRerankingService:
    """Enterprise domain service executing Cross-Encoder pair reranking on candidate pools.

    Core Responsibilities:
    1. Tenant Isolation: Validates that every candidate chunk strictly belongs to the tenant.
    2. Input Bounding: Enforces candidate limits and token-length bounds to protect resources.
    3. Context Composition: Enriches candidate text with headings without mutating chunk.
    4. Controlled Concurrency: Bounded batch inference via asyncio Semaphore and timeout deadline.
    5. Provenance & Score: Retains dense, sparse, and RRF ranks alongside rerank scores.
    6. Graceful Degradation: Falls back to RRF ranking if neural inference fails when configured.
    """

    def __init__(
        self,
        provider: RerankerProvider | None = None,
        config: RerankerConfig | None = None,
    ) -> None:
        self.config = config or get_reranker_config()
        self.provider = provider or RerankerProviderFactory.create(self.config)
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_batches)

    async def rerank(
        self,
        query: str,
        candidates: list[FusedCandidate],
        organization_id: UUID,
        *,
        top_k: int | None = None,
        max_candidates: int | None = None,
    ) -> RerankingResult:
        """Score and rerank a candidate pool using cross-encoder query-candidate interaction."""
        t_global_start = time.perf_counter()

        if not candidates:
            return RerankingResult(
                candidates=[],
                diagnostics=RerankingDiagnostics(
                    provider=self.provider.provider_name,
                    model=self.provider.model_name,
                    version=self.provider.version,
                    device=self.provider.device,
                    candidate_count=0,
                    reranked_count=0,
                    batch_count=0,
                    is_degraded=False,
                    latency=RerankingLatency(),
                ),
            )

        # 1. Validation & Tenant Isolation Guardrail
        cleaned_query = RerankerValidator.validate_query(query)
        RerankerValidator.validate_tenant_boundary(candidates, organization_id)

        # 2. Bound Candidate Pool
        bounded_candidates = RerankerValidator.bound_candidates(
            candidates=candidates,
            config=self.config,
            requested_limit=max_candidates,
        )

        # 3. Construct (query, text) Pairs with Heading Context
        pairs: list[tuple[str, str]] = []
        for cand in bounded_candidates:
            raw_text = str(cand.payload.get("text", "")).strip()
            headings = cand.payload.get("heading_hierarchy") or []
            if headings and isinstance(headings, list):
                prefix = " > ".join(str(h) for h in headings if h)
                enriched_text = f"{prefix}\n\n{raw_text}" if prefix else raw_text
            else:
                enriched_text = raw_text

            bounded_text = RerankerValidator.truncate_text_if_needed(
                text=enriched_text,
                max_tokens=self.config.max_input_tokens,
            )
            pairs.append((cleaned_query, bounded_text))

        # 4. Batch Pairs & Execute Controlled Concurrency Scoring
        batches = create_batches(pairs, self.config.batch_size)
        is_degraded = False
        degradation_reason: str | None = None
        scores: list[float] = []

        t_infer_start = time.perf_counter()
        try:

            async def _score_batch(batch_pairs: list[tuple[str, str]]) -> list[float]:
                async with self._semaphore:
                    return await self.provider.score_pairs(batch_pairs)

            batch_tasks = [_score_batch(b) for b in batches]
            batch_results = await asyncio.wait_for(
                asyncio.gather(*batch_tasks),
                timeout=self.config.timeout_seconds,
            )
            for b_scores in batch_results:
                scores.extend(b_scores)

        except TimeoutError as exc:
            elapsed = (time.perf_counter() - t_global_start) * 1000.0
            logger.error(
                "Reranking inference timed out after %.2fms (limit: %.2fs)",
                elapsed,
                self.config.timeout_seconds,
            )
            if not self.config.allow_fallback:
                raise RerankerTimeoutError(
                    f"Reranking timed out after {self.config.timeout_seconds}s."
                ) from exc
            is_degraded = True
            degradation_reason = (
                f"Reranking inference timed out ({self.config.timeout_seconds}s limit)"
            )
        except Exception as exc:
            logger.warning("Reranking failed with error: %s", exc)
            if not self.config.allow_fallback:
                if isinstance(exc, RerankingError):
                    raise
                raise RerankingError(f"Reranking failed: {exc}") from exc
            is_degraded = True
            degradation_reason = f"Reranker unavailable: {exc}"

        t_infer_elapsed = (time.perf_counter() - t_infer_start) * 1000.0

        # 5. Build Reranked Candidate List
        reranked_candidates: list[RerankedCandidate] = []
        if is_degraded or len(scores) != len(bounded_candidates):
            # Fallback to RRF ordering
            for rrf_rank, cand in enumerate(bounded_candidates, start=1):
                reranked_candidates.append(
                    RerankedCandidate(
                        chunk_id=cand.chunk_id,
                        document_id=cand.document_id,
                        organization_id=cand.organization_id,
                        rerank_score=cand.rrf_score,
                        rerank_rank=rrf_rank,
                        original_rrf_rank=cand.rank or rrf_rank,
                        dense_score=cand.dense_score,
                        dense_rank=cand.dense_rank,
                        sparse_score=cand.sparse_score,
                        sparse_rank=cand.sparse_rank,
                        rrf_score=cand.rrf_score,
                        payload=cand.payload,
                    )
                )
        else:
            # Pair scores with candidates
            scored_candidates: list[tuple[float, FusedCandidate]] = []
            for score, cand in zip(scores, bounded_candidates, strict=False):
                scored_candidates.append((score, cand))

            # Sort descending by rerank_score with deterministic tie-breakers
            scored_candidates.sort(
                key=lambda pair: (
                    -pair[0],
                    -(pair[1].rrf_score if pair[1].rrf_score is not None else 0.0),
                    -(pair[1].dense_score if pair[1].dense_score is not None else -9999.0),
                    str(pair[1].chunk_id),
                )
            )

            # Assign 1-indexed rerank_rank
            for rank_idx, (sc, cand) in enumerate(scored_candidates, start=1):
                reranked_candidates.append(
                    RerankedCandidate(
                        chunk_id=cand.chunk_id,
                        document_id=cand.document_id,
                        organization_id=cand.organization_id,
                        rerank_score=round(float(sc), 6),
                        rerank_rank=rank_idx,
                        original_rrf_rank=cand.rank or rank_idx,
                        dense_score=cand.dense_score,
                        dense_rank=cand.dense_rank,
                        sparse_score=cand.sparse_score,
                        sparse_rank=cand.sparse_rank,
                        rrf_score=cand.rrf_score,
                        payload=cand.payload,
                    )
                )

        # 6. Apply Final Top-K Selection
        final_k = min(
            top_k if top_k is not None else self.config.final_k,
            len(reranked_candidates),
        )
        final_candidates = reranked_candidates[:final_k]

        t_total_elapsed = (time.perf_counter() - t_global_start) * 1000.0

        diagnostics = RerankingDiagnostics(
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            version=self.provider.version,
            device=self.provider.device,
            candidate_count=len(bounded_candidates),
            reranked_count=len(final_candidates),
            batch_count=len(batches),
            is_degraded=is_degraded,
            degradation_reason=degradation_reason,
            latency=RerankingLatency(
                inference_ms=round(t_infer_elapsed, 3),
                total_ms=round(t_total_elapsed, 3),
            ),
        )

        return RerankingResult(
            candidates=final_candidates,
            diagnostics=diagnostics,
        )

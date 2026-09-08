"""Domain service orchestrating concurrent Hybrid Retrieval and Reciprocal Rank Fusion."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentChunk
from app.repositories.chunk import DocumentChunkRepository
from app.retrieval.config import HybridRetrievalConfig, get_hybrid_retrieval_config

if TYPE_CHECKING:
    from app.query.multi_retrieval import MultiQueryRetrievalService
    from app.query.service import QueryUnderstandingService
    from app.reranking.service import CrossEncoderRerankingService
from app.retrieval.exceptions import (
    RetrievalError,
    RetrievalTimeoutError,
)
from app.retrieval.hybrid.models import (
    FusedCandidate,
    HybridRetrievalDiagnostics,
    HybridRetrievalLatency,
    HybridRetrievalResult,
    HybridRetrievedChunk,
)
from app.retrieval.hybrid.rrf import ReciprocalRankFusion
from app.retrieval.service import DenseRetrievalService
from app.retrieval.sparse.service import SparseRetrievalService
from app.vectorstore.models import VectorSearchResult

logger = logging.getLogger(__name__)


class HybridRetrievalService:
    """Enterprise domain service executing concurrent hybrid retrieval with RRF.

    Architecture & Concurrency:
    1. Runs Dense Search (Task 12) and Sparse BM25 Search concurrently via asyncio.gather.
    2. Coordinates shared timeout budget; cancels pending tasks on timeout.
    3. Handles partial failures gracefully: provides fallback diagnostics if either pathway fails.
    4. Executes Reciprocal Rank Fusion (RRF) with candidate deduplication.
    5. Optionally executes Cross-Encoder Reranking on fused candidate pool.
    6. Hydrates chunks and parent context strictly AFTER reranking on top-K (0 N+1).
    7. Assembles comprehensive explainability diagnostics (individual ranks, scores, latencies).
    """

    def __init__(
        self,
        dense_service: DenseRetrievalService,
        sparse_service: SparseRetrievalService,
        chunk_repository: DocumentChunkRepository | None = None,
        config: HybridRetrievalConfig | None = None,
        reranker_service: CrossEncoderRerankingService | None = None,
        query_understanding_service: QueryUnderstandingService | None = None,
        multi_query_service: MultiQueryRetrievalService | None = None,
    ) -> None:
        self.dense_service = dense_service
        self.sparse_service = sparse_service
        self.chunk_repository = chunk_repository or DocumentChunkRepository()
        self.config = config or get_hybrid_retrieval_config()
        self.reranker_service = reranker_service
        self.query_understanding_service = query_understanding_service
        self.multi_query_service = multi_query_service

    async def search(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        query: str,
        *,
        top_k: int | None = None,
        dense_candidate_k: int | None = None,
        sparse_candidate_k: int | None = None,
        rrf_k: int | None = None,
        rerank: bool | None = None,
        rerank_candidates: int | None = None,
        document_id: uuid.UUID | None = None,
        chunk_type: str | None = None,
        page_number: int | None = None,
        section: str | None = None,
        score_threshold: float | None = None,
        include_parent: bool | None = None,
        enable_query_understanding: bool | None = None,
        enable_query_rewrite: bool | None = None,
        enable_query_expansion: bool | None = None,
        enable_query_decomposition: bool | None = None,
    ) -> HybridRetrievalResult:
        """Execute concurrent hybrid dense + sparse retrieval with RRF and reranking."""
        t_global_start = time.perf_counter()

        final_top_k = min(
            top_k if top_k is not None else self.config.default_top_k,
            self.config.max_top_k,
        )
        eff_dense_k = min(
            dense_candidate_k if dense_candidate_k is not None else self.config.dense_candidate_k,
            200,
        )
        eff_sparse_k = min(
            sparse_candidate_k
            if sparse_candidate_k is not None
            else self.config.sparse_candidate_k,
            200,
        )
        eff_rrf_k = rrf_k if rrf_k is not None else self.config.rrf_k
        should_include_parent = include_parent if include_parent is not None else True

        # Determine whether to execute cross-encoder reranking
        is_rerank_available = (
            self.reranker_service is not None and self.reranker_service.config.enabled
        )
        should_rerank = rerank if rerank is not None else is_rerank_available

        # Check if Query Understanding should be executed
        if enable_query_understanding and self.query_understanding_service is not None:
            plan = await self.query_understanding_service.analyze_and_plan(
                query=query,
                organization_id=organization_id,
                enable_rewrite=enable_query_rewrite,
                enable_expansion=enable_query_expansion,
                enable_decomposition=enable_query_decomposition,
            )
            # If multi-query plan produced multiple queries and multi_query_service is wired
            if self.multi_query_service is not None and len(plan.all_queries) > 1:
                mq_res = await self.multi_query_service.execute_plan(
                    session=session,
                    organization_id=organization_id,
                    plan=plan,
                    top_k=final_top_k,
                    rerank=should_rerank,
                    rerank_candidates=rerank_candidates,
                    document_id=document_id,
                    chunk_type=chunk_type,
                    include_parent=should_include_parent,
                )
                diag = HybridRetrievalDiagnostics(
                    collection_name="tenant_chunks",
                    dense_candidate_count=len(mq_res.chunks),
                    sparse_candidate_count=len(mq_res.chunks),
                    merged_candidate_count=len(mq_res.chunks),
                    final_result_count=len(mq_res.chunks),
                    rrf_k=eff_rrf_k,
                    dense_candidate_k=eff_dense_k,
                    sparse_candidate_k=eff_sparse_k,
                    final_top_k=final_top_k,
                    reranking_enabled=should_rerank,
                    latency=HybridRetrievalLatency(total_ms=mq_res.total_latency_ms),
                )
                return HybridRetrievalResult(
                    query=query,
                    retrieval_mode=mq_res.retrieval_mode,
                    chunks=mq_res.chunks,
                    diagnostics=diag,
                )
            # If plan resolved a rewritten primary query, use it for retrieval
            query = plan.primary_query

        # Candidate pool size for RRF fusion before reranking
        if should_rerank and self.reranker_service is not None:
            max_cands = (
                rerank_candidates
                if rerank_candidates is not None
                else self.reranker_service.config.max_candidates
            )
            rrf_pool_k = min(max(max_cands, final_top_k), 200)
        else:
            rrf_pool_k = final_top_k

        # Define parallel worker coroutines
        async def _retrieve_dense() -> tuple[list[VectorSearchResult], float, str]:
            cands, lat, coll, *rest = await self.dense_service.retrieve_candidates(
                organization_id=organization_id,
                query=query,
                top_k=eff_dense_k,
                document_id=document_id,
                chunk_type=chunk_type,
                page_number=page_number,
                section=section,
                score_threshold=score_threshold,
            )
            return cands, lat, coll

        async def _retrieve_sparse() -> tuple[list[VectorSearchResult], float]:
            res = await self.sparse_service.search(
                organization_id=organization_id,
                query=query,
                top_k=eff_sparse_k,
                document_id=document_id,
                chunk_type=chunk_type,
                page_number=page_number,
                section=section,
                score_threshold=score_threshold,
            )
            return res.candidates, res.latency_ms

        # Execute concurrent tasks bounded by shared timeout budget
        try:
            dense_output, sparse_output = await asyncio.wait_for(
                asyncio.gather(
                    _retrieve_dense(),
                    _retrieve_sparse(),
                    return_exceptions=True,
                ),
                timeout=self.config.timeout_seconds,
            )
        except TimeoutError as exc:
            elapsed = (time.perf_counter() - t_global_start) * 1000.0
            logger.error(
                "Hybrid retrieval timed out after %.2fms (limit: %.2fs)",
                elapsed,
                self.config.timeout_seconds,
            )
            raise RetrievalTimeoutError(
                f"Hybrid retrieval timed out after {self.config.timeout_seconds}s.",
                details={"timeout_seconds": self.config.timeout_seconds, "elapsed_ms": elapsed},
            ) from exc

        # Process dense pathway output
        dense_candidates: list[VectorSearchResult] = []
        dense_latency_ms: float = 0.0
        collection_name: str = ""
        dense_error: str | None = None

        if isinstance(dense_output, BaseException):
            dense_error = str(dense_output)
            logger.warning("Dense retrieval pathway failed: %s", dense_output)
        else:
            dense_candidates, dense_latency_ms, collection_name = dense_output

        # Process sparse pathway output
        sparse_candidates: list[VectorSearchResult] = []
        sparse_latency_ms: float = 0.0
        sparse_error: str | None = None

        if isinstance(sparse_output, BaseException):
            sparse_error = str(sparse_output)
            logger.warning("Sparse retrieval pathway failed: %s", sparse_output)
        else:
            sparse_candidates, sparse_latency_ms = sparse_output

        # Handle complete failure
        if dense_error and sparse_error:
            logger.error("Both dense and sparse retrieval failed completely.")
            err_msg = (
                f"Hybrid retrieval failed on both pathways: Dense: [{dense_error}], "
                f"Sparse: [{sparse_error}]"
            )
            raise RetrievalError(err_msg)

        # Handle partial failure & determine operational mode
        is_degraded = False
        degradation_reason: str | None = None
        retrieval_mode = "hybrid"

        if dense_error:
            if not self.config.allow_partial_failure:
                raise RetrievalError(f"Dense retrieval failed: {dense_error}")
            is_degraded = True
            degradation_reason = f"Dense retrieval unavailable: {dense_error}"
            retrieval_mode = "sparse_fallback"
        elif sparse_error:
            if not self.config.allow_partial_failure:
                raise RetrievalError(f"Sparse retrieval failed: {sparse_error}")
            is_degraded = True
            degradation_reason = f"Sparse retrieval unavailable: {sparse_error}"
            retrieval_mode = "dense_fallback"

        # 4. Reciprocal Rank Fusion (RRF)
        t_fuse0 = time.perf_counter()
        fused_candidates = ReciprocalRankFusion.fuse(
            dense_candidates=dense_candidates,
            sparse_candidates=sparse_candidates,
            rrf_k=eff_rrf_k,
            top_k=rrf_pool_k,
        )
        fusion_latency_ms = round((time.perf_counter() - t_fuse0) * 1000.0, 3)

        # 5. Cross-Encoder Reranking Phase
        rerank_latency_ms = 0.0
        final_candidates: list[FusedCandidate] = []
        reranking_enabled = False
        reranker_provider_name: str | None = None
        reranker_model_name: str | None = None
        reranker_version_str: str | None = None
        reranker_cand_count = 0

        if should_rerank and self.reranker_service is not None and fused_candidates:
            reranking_enabled = True
            reranker_provider_name = self.reranker_service.provider.provider_name
            reranker_model_name = self.reranker_service.provider.model_name
            reranker_version_str = self.reranker_service.provider.version

            t_rrk0 = time.perf_counter()
            rerank_result = await self.reranker_service.rerank(
                query=query,
                candidates=fused_candidates,
                organization_id=organization_id,
                top_k=final_top_k,
                max_candidates=rerank_candidates,
            )
            rerank_latency_ms = round((time.perf_counter() - t_rrk0) * 1000.0, 3)
            reranker_cand_count = rerank_result.diagnostics.candidate_count

            if rerank_result.diagnostics.is_degraded:
                is_degraded = True
                degradation_reason = rerank_result.diagnostics.degradation_reason or (
                    "Reranking degraded"
                )

            # Convert RerankedCandidate back to FusedCandidate for hydration
            for rc in rerank_result.candidates:
                final_candidates.append(
                    FusedCandidate(
                        chunk_id=rc.chunk_id,
                        document_id=rc.document_id,
                        organization_id=rc.organization_id,
                        rrf_score=rc.rrf_score if rc.rrf_score is not None else 0.0,
                        rank=rc.rerank_rank,
                        dense_score=rc.dense_score,
                        dense_rank=rc.dense_rank,
                        sparse_score=rc.sparse_score,
                        sparse_rank=rc.sparse_rank,
                        rerank_score=rc.rerank_score,
                        rerank_rank=rc.rerank_rank,
                        original_rrf_rank=rc.original_rrf_rank,
                        payload=rc.payload,
                    )
                )

            if retrieval_mode == "hybrid" and not is_degraded:
                retrieval_mode = "hybrid_reranked"
        else:
            final_candidates = fused_candidates[:final_top_k]

        # 6. Zero N+1 Batch Parent & Chunk Hydration
        t_hyd0 = time.perf_counter()
        hydrated_chunks = await self._hydrate_fused_candidates(
            session=session,
            organization_id=organization_id,
            fused_candidates=final_candidates,
            include_parent=should_include_parent,
            retrieval_mode=retrieval_mode,
        )
        hydration_latency_ms = round((time.perf_counter() - t_hyd0) * 1000.0, 3)

        total_latency_ms = round((time.perf_counter() - t_global_start) * 1000.0, 3)

        # 7. Assemble Execution Diagnostics
        diagnostics = HybridRetrievalDiagnostics(
            collection_name=collection_name or "hybrid_collection",
            dense_candidate_count=len(dense_candidates),
            sparse_candidate_count=len(sparse_candidates),
            merged_candidate_count=len(fused_candidates),
            final_result_count=len(hydrated_chunks),
            rrf_k=eff_rrf_k,
            dense_candidate_k=eff_dense_k,
            sparse_candidate_k=eff_sparse_k,
            final_top_k=final_top_k,
            reranking_enabled=reranking_enabled,
            reranker_provider=reranker_provider_name,
            reranker_model=reranker_model_name,
            reranker_version=reranker_version_str,
            reranker_candidate_count=reranker_cand_count,
            is_degraded=is_degraded,
            degradation_reason=degradation_reason,
            latency=HybridRetrievalLatency(
                dense_ms=round(dense_latency_ms, 3),
                sparse_ms=round(sparse_latency_ms, 3),
                fusion_ms=fusion_latency_ms,
                rerank_ms=rerank_latency_ms,
                hydration_ms=hydration_latency_ms,
                total_ms=total_latency_ms,
            ),
        )

        return HybridRetrievalResult(
            query=query,
            retrieval_mode=retrieval_mode,
            chunks=hydrated_chunks,
            diagnostics=diagnostics,
        )

    async def _hydrate_fused_candidates(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        fused_candidates: list[FusedCandidate],
        include_parent: bool,
        retrieval_mode: str,
    ) -> list[HybridRetrievedChunk]:
        """Hydrate matched candidates from DB using single batch query (plus 1 for parents)."""
        if not fused_candidates:
            return []

        # Extract target chunk IDs from candidates
        chunk_ids: list[uuid.UUID] = []
        for fc in fused_candidates:
            raw_cid = fc.payload.get("chunk_id")
            if raw_cid:
                try:
                    chunk_ids.append(uuid.UUID(str(raw_cid)))
                except ValueError:
                    chunk_ids.append(fc.chunk_id)
            else:
                chunk_ids.append(fc.chunk_id)

        # Batch query 1: Fetch all matched chunks for this tenant
        db_chunks = await self.chunk_repository.get_by_ids(
            session=session,
            ids=chunk_ids,
            organization_id=organization_id,
        )
        chunks_by_id: dict[uuid.UUID, DocumentChunk] = {c.id: c for c in db_chunks}

        # Batch query 2: Fetch parent chunks if requested (strictly zero N+1)
        parents_by_id: dict[uuid.UUID, DocumentChunk] = {}
        if include_parent:
            parent_ids: list[uuid.UUID] = [
                c.parent_chunk_id for c in db_chunks if c.parent_chunk_id is not None
            ]
            if parent_ids:
                parent_records = await self.chunk_repository.get_by_ids(
                    session=session,
                    ids=parent_ids,
                    organization_id=organization_id,
                )
                parents_by_id = {p.id: p for p in parent_records}

        # Build HybridRetrievedChunk preserving exact RRF order
        results: list[HybridRetrievedChunk] = []
        for fc in fused_candidates:
            raw_cid = fc.payload.get("chunk_id")
            cid = uuid.UUID(str(raw_cid)) if raw_cid else fc.chunk_id
            db_chunk = chunks_by_id.get(cid)
            payload = fc.payload

            text = db_chunk.content if db_chunk else str(payload.get("text", ""))
            chunk_index = db_chunk.chunk_index if db_chunk else int(payload.get("chunk_index", 0))
            chunk_type = (
                db_chunk.chunk_type
                if (db_chunk and db_chunk.chunk_type)
                else str(payload.get("chunk_type") or "text")
            )
            token_count = db_chunk.token_count if db_chunk else int(payload.get("token_count", 0))
            char_count = (
                db_chunk.character_count
                if db_chunk
                else int(payload.get("character_count", len(text)))
            )
            page_number = (
                db_chunk.page_number
                if (db_chunk and db_chunk.page_number is not None)
                else payload.get("page_number")
            )
            page_end = (
                (db_chunk.source_locator.get("page_end") if db_chunk.source_locator else None)
                if db_chunk
                else payload.get("page_end")
            )
            section = (
                db_chunk.section
                if (db_chunk and db_chunk.section is not None)
                else payload.get("section")
            )
            heading_hierarchy = list(payload.get("heading_hierarchy") or [])

            parent_chunk_id = db_chunk.parent_chunk_id if db_chunk else None
            parent_text = (
                parents_by_id[parent_chunk_id].content
                if (parent_chunk_id and parent_chunk_id in parents_by_id)
                else None
            )

            # Primary score is rerank_score if reranked, else rrf_score
            primary_score = fc.rerank_score if fc.rerank_score is not None else fc.rrf_score

            results.append(
                HybridRetrievedChunk(
                    chunk_id=cid,
                    document_id=fc.document_id,
                    organization_id=organization_id,
                    score=primary_score,
                    text=text,
                    chunk_index=chunk_index,
                    chunk_type=chunk_type,
                    token_count=token_count,
                    character_count=char_count,
                    page_number=page_number,
                    page_end=page_end,
                    section=section,
                    heading_hierarchy=heading_hierarchy,
                    parent_chunk_id=parent_chunk_id,
                    parent_text=parent_text,
                    metadata=payload,
                    retrieval_mode=retrieval_mode,
                    rrf_score=fc.rrf_score,
                    dense_score=fc.dense_score,
                    dense_rank=fc.dense_rank,
                    sparse_score=fc.sparse_score,
                    sparse_rank=fc.sparse_rank,
                    rerank_score=fc.rerank_score,
                    rerank_rank=fc.rerank_rank,
                    original_rank=fc.original_rrf_rank or fc.rank,
                )
            )

        return results

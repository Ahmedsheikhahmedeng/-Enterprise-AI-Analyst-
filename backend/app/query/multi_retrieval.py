"""Multi-query retrieval orchestrator executing Cross-Query RRF Fusion and Reranking."""

import asyncio
import contextlib
import logging
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.query.models import MultiQueryRetrievalResult, SearchPlan
from app.repositories.chunk import DocumentChunkRepository
from app.reranking.service import CrossEncoderRerankingService
from app.retrieval.hybrid.models import (
    FusedCandidate,
    HybridRetrievedChunk,
)
from app.retrieval.hybrid.service import HybridRetrievalService

logger = logging.getLogger(__name__)


class MultiQueryRetrievalService:
    """Coordinates multi-query parallel retrieval, Cross-Query RRF, and post-rerank hydration."""

    def __init__(
        self,
        hybrid_service: HybridRetrievalService,
        reranker_service: CrossEncoderRerankingService | None = None,
        chunk_repository: DocumentChunkRepository | None = None,
    ) -> None:
        self.hybrid_service = hybrid_service
        self.reranker_service = reranker_service or hybrid_service.reranker_service
        self.chunk_repository = chunk_repository or DocumentChunkRepository()

    async def execute_plan(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        plan: SearchPlan,
        *,
        top_k: int = 10,
        rerank: bool | None = None,
        rerank_candidates: int | None = None,
        document_id: uuid.UUID | None = None,
        chunk_type: str | None = None,
        include_parent: bool = True,
    ) -> MultiQueryRetrievalResult:
        """Execute multi-query hybrid retrieval plan with cross-query RRF and reranking."""
        t_global_start = time.perf_counter()

        planned_queries = plan.all_queries
        if not planned_queries:
            planned_queries = [plan.original_query]

        # Weight assignment: primary=1.0, subquery=0.9, alternative=0.8
        def get_weight(q: str) -> float:
            if q == plan.primary_query:
                return 1.0
            if q in plan.sub_queries:
                return 0.9
            return 0.8

        # 1. Execute parallel hybrid retrieval for all queries
        # Note: We run individual hybrid searches with rerank=False and include_parent=False
        # because cross-encoder reranking and hydration are executed once on the fused pool!
        async def _search_single_query(query_str: str) -> list[HybridRetrievedChunk]:
            try:
                res = await self.hybrid_service.search(
                    session=session,
                    organization_id=organization_id,
                    query=query_str,
                    top_k=plan.retrieval_budget.max_candidates_per_query,
                    rerank=False,
                    include_parent=False,
                    document_id=document_id,
                    chunk_type=chunk_type,
                )
                return res.chunks
            except Exception as exc:
                logger.warning("Retrieval failed for query variant '%s': %s", query_str, exc)
                return []

        search_tasks = [_search_single_query(q) for q in planned_queries]
        results_per_query: list[list[HybridRetrievedChunk]] = await asyncio.gather(*search_tasks)

        # 2. Cross-Query Reciprocal Rank Fusion (Cross-Query RRF)
        # Combine candidate occurrences across all query formulations
        rrf_constant = 60.0
        candidate_map: dict[uuid.UUID, dict[str, Any]] = {}

        for q_str, chunk_list in zip(planned_queries, results_per_query, strict=False):
            weight = get_weight(q_str)
            for rank_0, chunk in enumerate(chunk_list):
                cand_rank = rank_0 + 1
                reciprocal_score = weight / (rrf_constant + cand_rank)

                cid = chunk.chunk_id
                if cid not in candidate_map:
                    candidate_map[cid] = {
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "organization_id": chunk.organization_id,
                        "rrf_score": 0.0,
                        "dense_score": chunk.dense_score,
                        "dense_rank": chunk.dense_rank,
                        "sparse_score": chunk.sparse_score,
                        "sparse_rank": chunk.sparse_rank,
                        "payload": {
                            "text": chunk.text,
                            "heading_hierarchy": chunk.heading_hierarchy,
                            "section": chunk.section,
                            "page_number": chunk.page_number,
                            "page_end": chunk.page_end,
                            "chunk_index": chunk.chunk_index,
                            "chunk_type": chunk.chunk_type,
                            "token_count": chunk.token_count,
                            "character_count": chunk.character_count,
                            "parent_chunk_id": chunk.parent_chunk_id,
                            "document_name": chunk.metadata.get("document_name"),
                            "metadata": chunk.metadata,
                        },
                    }
                candidate_map[cid]["rrf_score"] += reciprocal_score

        # Sort cross-query fused candidates by aggregated RRF score
        sorted_cands = sorted(
            candidate_map.values(),
            key=lambda c: (-c["rrf_score"], str(c["chunk_id"])),
        )

        # Cap fused candidate pool to budget
        max_cands = min(
            rerank_candidates if rerank_candidates is not None else 50,
            plan.retrieval_budget.max_total_candidates,
        )
        fused_pool: list[FusedCandidate] = []
        for idx, item in enumerate(sorted_cands[:max_cands]):
            fused_pool.append(
                FusedCandidate(
                    chunk_id=item["chunk_id"],
                    document_id=item["document_id"],
                    organization_id=item["organization_id"],
                    rrf_score=round(float(item["rrf_score"]), 6),
                    rank=idx + 1,
                    dense_score=item["dense_score"],
                    dense_rank=item["dense_rank"],
                    sparse_score=item["sparse_score"],
                    sparse_rank=item["sparse_rank"],
                    payload=item["payload"],
                )
            )

        # 3. Cross-Encoder Reranking
        should_rerank = (
            rerank
            if rerank is not None
            else (self.reranker_service is not None and self.reranker_service.config.enabled)
        )

        final_candidates: list[FusedCandidate] = []
        if should_rerank and self.reranker_service is not None and fused_pool:
            try:
                rerank_result = await self.reranker_service.rerank(
                    query=plan.original_query,
                    candidates=fused_pool,
                    organization_id=organization_id,
                    top_k=top_k,
                    max_candidates=len(fused_pool),
                )
                for rc in rerank_result.candidates:
                    # Map back to FusedCandidate preserving rerank scores
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
            except Exception as exc:
                logger.warning("Cross-Encoder reranking failed on fused pool: %s", exc)
                final_candidates = fused_pool[:top_k]
        else:
            final_candidates = fused_pool[:top_k]

        # 4. Batch Parent Chunk Hydration (Zero N+1)
        final_chunks: list[HybridRetrievedChunk] = []
        parent_texts_by_id: dict[uuid.UUID, str] = {}

        if include_parent and final_candidates:
            parent_ids_to_fetch: set[uuid.UUID] = set()
            for c in final_candidates:
                raw_pid = c.payload.get("parent_chunk_id")
                if raw_pid is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        parent_ids_to_fetch.add(
                            raw_pid if isinstance(raw_pid, uuid.UUID) else uuid.UUID(str(raw_pid))
                        )
            if parent_ids_to_fetch:
                parent_models = await self.chunk_repository.get_by_ids(
                    session=session,
                    ids=list(parent_ids_to_fetch),
                    organization_id=organization_id,
                )
                parent_texts_by_id = {p.id: p.content for p in parent_models}

        for cand in final_candidates:
            p_id = cand.payload.get("parent_chunk_id")
            p_text = parent_texts_by_id.get(p_id) if p_id else None

            final_chunks.append(
                HybridRetrievedChunk(
                    chunk_id=cand.chunk_id,
                    document_id=cand.document_id,
                    organization_id=cand.organization_id,
                    score=cand.rerank_score if cand.rerank_score is not None else cand.rrf_score,
                    text=str(cand.payload.get("text", "")),
                    chunk_index=int(cand.payload.get("chunk_index", 0)),
                    chunk_type=str(cand.payload.get("chunk_type", "sentence")),
                    token_count=int(cand.payload.get("token_count", 0)),
                    character_count=int(cand.payload.get("character_count", 0)),
                    page_number=cand.payload.get("page_number"),
                    page_end=cand.payload.get("page_end"),
                    section=cand.payload.get("section"),
                    heading_hierarchy=cand.payload.get("heading_hierarchy", []),
                    parent_chunk_id=p_id,
                    parent_text=p_text,
                    retrieval_mode=(
                        "multi_query_hybrid_reranked"
                        if cand.rerank_score is not None
                        else "multi_query_hybrid"
                    ),
                    rrf_score=cand.rrf_score,
                    dense_score=cand.dense_score,
                    dense_rank=cand.dense_rank,
                    sparse_score=cand.sparse_score,
                    sparse_rank=cand.sparse_rank,
                    rerank_score=cand.rerank_score,
                    rerank_rank=cand.rerank_rank,
                    original_rank=cand.original_rrf_rank or cand.rank,
                    metadata=dict(cand.payload.get("metadata") or cand.payload),
                )
            )

        total_elapsed_ms = round((time.perf_counter() - t_global_start) * 1000.0, 3)

        return MultiQueryRetrievalResult(
            original_query=plan.original_query,
            search_plan=plan,
            chunks=final_chunks,
            retrieval_mode="multi_query_hybrid_reranked" if should_rerank else "multi_query_hybrid",
            total_results=len(final_chunks),
            total_latency_ms=total_elapsed_ms,
        )

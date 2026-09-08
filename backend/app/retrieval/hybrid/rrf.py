"""Reciprocal Rank Fusion (RRF) algorithm for combining dense and sparse candidate rankings."""

import uuid

from app.retrieval.hybrid.models import FusedCandidate
from app.vectorstore.models import VectorSearchResult


class ReciprocalRankFusion:
    """Reciprocal Rank Fusion (RRF) combiner.

    Mathematical Basis:
        RRF_score(d) = Σ_{m ∈ M} (1 / (k + rank_m(d)))

    Where:
        - M is the set of retrieval modalities (e.g. dense, sparse).
        - rank_m(d) is the 1-based ordinal ranking of document d in modality m.
        - k is the RRF smoothing constant (typically 60).

    Design Principles:
        - NEVER adds raw dense and sparse similarity scores.
        - Deduplicates candidates appearing in both modalities.
        - Preserves explainability: individual ranks and scores are tracked on each candidate.
        - Deterministic tie-breaking for predictable, reproducible rankings.
    """

    @classmethod
    def fuse(
        cls,
        dense_candidates: list[VectorSearchResult],
        sparse_candidates: list[VectorSearchResult],
        *,
        rrf_k: int = 60,
        top_k: int | None = None,
    ) -> list[FusedCandidate]:
        """Combine dense and sparse candidate lists into a unified ranked list via RRF."""
        if not dense_candidates and not sparse_candidates:
            return []

        candidates_map: dict[uuid.UUID, FusedCandidate] = {}

        # 1. Process dense candidates (1-indexed)
        for rank_idx, cand in enumerate(dense_candidates, start=1):
            chunk_id = cand.id
            org_id_str = cand.payload.get("organization_id", "")
            doc_id_str = cand.payload.get("document_id", "")
            org_id = uuid.UUID(org_id_str) if org_id_str else chunk_id
            doc_id = uuid.UUID(doc_id_str) if doc_id_str else chunk_id

            score_contribution = 1.0 / (rrf_k + rank_idx)

            candidates_map[chunk_id] = FusedCandidate(
                chunk_id=chunk_id,
                document_id=doc_id,
                organization_id=org_id,
                rrf_score=score_contribution,
                dense_score=cand.score,
                dense_rank=rank_idx,
                payload=cand.payload,
            )

        # 2. Process sparse candidates (1-indexed)
        for rank_idx, cand in enumerate(sparse_candidates, start=1):
            chunk_id = cand.id
            score_contribution = 1.0 / (rrf_k + rank_idx)

            if chunk_id in candidates_map:
                # Merge into existing candidate
                existing = candidates_map[chunk_id]
                existing.rrf_score += score_contribution
                existing.sparse_score = cand.score
                existing.sparse_rank = rank_idx
            else:
                org_id_str = cand.payload.get("organization_id", "")
                doc_id_str = cand.payload.get("document_id", "")
                org_id = uuid.UUID(org_id_str) if org_id_str else chunk_id
                doc_id = uuid.UUID(doc_id_str) if doc_id_str else chunk_id

                candidates_map[chunk_id] = FusedCandidate(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    organization_id=org_id,
                    rrf_score=score_contribution,
                    sparse_score=cand.score,
                    sparse_rank=rank_idx,
                    payload=cand.payload,
                )

        # 3. Sort candidates descending by RRF score with deterministic tie-breaking
        # Tie breaker: dense_score desc, sparse_score desc, chunk_id string
        sorted_candidates = sorted(
            candidates_map.values(),
            key=lambda c: (
                -c.rrf_score,
                -(c.dense_score if c.dense_score is not None else -9999.0),
                -(c.sparse_score if c.sparse_score is not None else -9999.0),
                str(c.chunk_id),
            ),
        )

        # 4. Assign 1-indexed final ranks and round RRF score
        fused_results: list[FusedCandidate] = []
        limit = top_k if top_k is not None else len(sorted_candidates)
        for final_rank, fused_cand in enumerate(sorted_candidates[:limit], start=1):
            fused_cand.rank = final_rank
            fused_cand.rrf_score = round(fused_cand.rrf_score, 6)
            fused_results.append(fused_cand)

        return fused_results

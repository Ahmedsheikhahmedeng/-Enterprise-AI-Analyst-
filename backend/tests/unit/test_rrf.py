"""Unit tests for Reciprocal Rank Fusion (RRF) algorithm and deduplication."""

import uuid

from app.retrieval.hybrid.rrf import ReciprocalRankFusion
from app.vectorstore.models import VectorSearchResult


class TestReciprocalRankFusion:
    """Comprehensive test suite for RRF ranking, score tracking, and tie-breaking."""

    def test_standard_rrf_rank_fusion(self) -> None:
        """Verify the exact prompt scenario:

        Dense:  A=1, B=2, C=3
        Sparse: B=1, C=2, D=3
        Expected order: B (1/62 + 1/61), C (1/63 + 1/62), A (1/61), D (1/63)
        """
        id_a, id_b, id_c, id_d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

        dense = [
            VectorSearchResult(id=id_a, score=0.95, payload={"chunk_id": str(id_a)}),
            VectorSearchResult(id=id_b, score=0.85, payload={"chunk_id": str(id_b)}),
            VectorSearchResult(id=id_c, score=0.75, payload={"chunk_id": str(id_c)}),
        ]
        sparse = [
            VectorSearchResult(id=id_b, score=15.2, payload={"chunk_id": str(id_b)}),
            VectorSearchResult(id=id_c, score=12.1, payload={"chunk_id": str(id_c)}),
            VectorSearchResult(id=id_d, score=8.4, payload={"chunk_id": str(id_d)}),
        ]

        fused = ReciprocalRankFusion.fuse(dense, sparse, rrf_k=60)

        assert len(fused) == 4
        assert [c.chunk_id for c in fused] == [id_b, id_c, id_a, id_d]

        # Check explainability metadata
        b_cand = fused[0]
        assert b_cand.chunk_id == id_b
        assert b_cand.dense_rank == 2
        assert b_cand.dense_score == 0.85
        assert b_cand.sparse_rank == 1
        assert b_cand.sparse_score == 15.2
        assert b_cand.rank == 1

        a_cand = fused[2]
        assert a_cand.chunk_id == id_a
        assert a_cand.dense_rank == 1
        assert a_cand.sparse_rank is None
        assert a_cand.sparse_score is None
        assert a_cand.rank == 3

    def test_dense_only_candidates(self) -> None:
        """Verify RRF gracefully handles empty sparse candidate list."""
        id_1, id_2 = uuid.uuid4(), uuid.uuid4()
        dense = [
            VectorSearchResult(id=id_1, score=0.9, payload={"chunk_id": str(id_1)}),
            VectorSearchResult(id=id_2, score=0.8, payload={"chunk_id": str(id_2)}),
        ]
        fused = ReciprocalRankFusion.fuse(dense, [], rrf_k=60)
        assert len(fused) == 2
        assert fused[0].chunk_id == id_1
        assert fused[1].chunk_id == id_2

    def test_sparse_only_candidates(self) -> None:
        """Verify RRF gracefully handles empty dense candidate list."""
        id_1, id_2 = uuid.uuid4(), uuid.uuid4()
        sparse = [
            VectorSearchResult(id=id_1, score=10.0, payload={"chunk_id": str(id_1)}),
            VectorSearchResult(id=id_2, score=5.0, payload={"chunk_id": str(id_2)}),
        ]
        fused = ReciprocalRankFusion.fuse([], sparse, rrf_k=60)
        assert len(fused) == 2
        assert fused[0].chunk_id == id_1
        assert fused[1].chunk_id == id_2

    def test_both_empty_returns_empty_list(self) -> None:
        """Verify passing two empty lists returns empty list without error."""
        fused = ReciprocalRankFusion.fuse([], [], rrf_k=60)
        assert fused == []

    def test_configurable_rrf_k(self) -> None:
        """Verify RRF smoothing constant k impacts scoring."""
        id_1 = uuid.uuid4()
        dense = [VectorSearchResult(id=id_1, score=0.9, payload={"chunk_id": str(id_1)})]

        fused_60 = ReciprocalRankFusion.fuse(dense, [], rrf_k=60)
        fused_20 = ReciprocalRankFusion.fuse(dense, [], rrf_k=20)

        # 1 / (20 + 1) > 1 / (60 + 1)
        assert fused_20[0].rrf_score > fused_60[0].rrf_score

    def test_top_k_limiting(self) -> None:
        """Verify top_k parameter slices final fused results."""
        dense = [
            VectorSearchResult(id=uuid.uuid4(), score=0.9 - i * 0.05, payload={}) for i in range(10)
        ]
        fused = ReciprocalRankFusion.fuse(dense, [], top_k=3)
        assert len(fused) == 3
        assert [c.rank for c in fused] == [1, 2, 3]

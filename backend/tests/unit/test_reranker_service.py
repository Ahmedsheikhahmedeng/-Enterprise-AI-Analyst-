"""Unit tests for CrossEncoderRerankingService orchestrator and fallback handling."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.reranking.config import RerankerConfig
from app.reranking.exceptions import RerankerTenantError
from app.reranking.providers.local import LocalDeterministicCrossEncoderProvider
from app.reranking.service import CrossEncoderRerankingService
from app.retrieval.hybrid.models import FusedCandidate


class TestCrossEncoderRerankingService:
    """Unit test suite for CrossEncoderRerankingService."""

    @pytest.fixture
    def org_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture
    def service(self) -> CrossEncoderRerankingService:
        config = RerankerConfig(
            provider="local",
            max_candidates=10,
            final_k=3,
            allow_fallback=True,
        )
        provider = LocalDeterministicCrossEncoderProvider()
        return CrossEncoderRerankingService(provider=provider, config=config)

    @pytest.mark.asyncio
    async def test_rerank_orders_candidates_by_score_desc(
        self, service: CrossEncoderRerankingService, org_id: uuid.UUID
    ) -> None:
        """Verify candidates are re-ordered descending by cross-encoder score."""
        query = "What were total sales in 2025?"

        # Candidate 1: Weak match (mentions 2025, but about weather)
        c1 = FusedCandidate(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            organization_id=org_id,
            rrf_score=0.033,
            rank=1,
            dense_score=0.8,
            payload={"text": "In late 2025, unusually heavy rainfall occurred across Europe."},
        )
        # Candidate 2: Strong exact answer
        c2 = FusedCandidate(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            organization_id=org_id,
            rrf_score=0.030,
            rank=2,
            dense_score=0.75,
            payload={"text": "Total sales in 2025 reached an all-time record of $450 million."},
        )

        result = await service.rerank(
            query=query,
            candidates=[c1, c2],
            organization_id=org_id,
            top_k=2,
        )

        assert len(result.candidates) == 2
        # Strong answer (c2) should now be rank 1
        assert result.candidates[0].chunk_id == c2.chunk_id
        assert result.candidates[0].rerank_rank == 1
        assert result.candidates[0].original_rrf_rank == 2
        assert result.candidates[0].rerank_score > result.candidates[1].rerank_score

        # Weak answer (c1) should now be rank 2
        assert result.candidates[1].chunk_id == c1.chunk_id
        assert result.candidates[1].rerank_rank == 2
        assert result.candidates[1].original_rrf_rank == 1

    @pytest.mark.asyncio
    async def test_score_and_rank_provenance_preserved(
        self, service: CrossEncoderRerankingService, org_id: uuid.UUID
    ) -> None:
        """Verify original dense, sparse, and RRF scores and ranks are fully preserved."""
        c = FusedCandidate(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            organization_id=org_id,
            rrf_score=0.025,
            rank=4,
            dense_score=0.88,
            dense_rank=2,
            sparse_score=14.5,
            sparse_rank=5,
            payload={"text": "Executive summary of quarterly performance."},
        )
        result = await service.rerank(
            query="quarterly performance",
            candidates=[c],
            organization_id=org_id,
            top_k=1,
        )
        cand = result.candidates[0]
        assert cand.dense_score == 0.88
        assert cand.dense_rank == 2
        assert cand.sparse_score == 14.5
        assert cand.sparse_rank == 5
        assert cand.rrf_score == 0.025
        assert cand.original_rrf_rank == 4
        assert cand.rerank_rank == 1
        assert cand.rerank_score > 0.0

    @pytest.mark.asyncio
    async def test_candidate_pool_bounding(
        self, service: CrossEncoderRerankingService, org_id: uuid.UUID
    ) -> None:
        """Verify candidate pool is bounded to max_candidates."""
        candidates = [
            FusedCandidate(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                organization_id=org_id,
                rrf_score=0.01 * (20 - i),
                rank=i + 1,
                payload={"text": f"Chunk text {i}"},
            )
            for i in range(20)
        ]
        # service config max_candidates is 10
        result = await service.rerank(
            query="test query",
            candidates=candidates,
            organization_id=org_id,
            top_k=5,
        )
        assert result.diagnostics.candidate_count == 10
        assert len(result.candidates) == 5

    @pytest.mark.asyncio
    async def test_empty_candidate_pool(
        self, service: CrossEncoderRerankingService, org_id: uuid.UUID
    ) -> None:
        """Verify empty candidates returns empty result without error."""
        result = await service.rerank(
            query="empty query",
            candidates=[],
            organization_id=org_id,
            top_k=5,
        )
        assert result.candidates == []
        assert result.diagnostics.candidate_count == 0
        assert result.diagnostics.is_degraded is False

    @pytest.mark.asyncio
    async def test_tenant_boundary_violation_raises(
        self, service: CrossEncoderRerankingService, org_id: uuid.UUID
    ) -> None:
        """Verify candidate from different organization raises RerankerTenantError."""
        other_org = uuid.uuid4()
        cand = FusedCandidate(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            organization_id=other_org,
            rrf_score=0.03,
            payload={"text": "Sensitive corporate data."},
        )
        with pytest.raises(RerankerTenantError):
            await service.rerank(
                query="Sensitive corporate data",
                candidates=[cand],
                organization_id=org_id,
            )

    @pytest.mark.asyncio
    async def test_fallback_to_rrf_on_provider_failure(self, org_id: uuid.UUID) -> None:
        """Verify when provider fails, service degrades gracefully to RRF ranking."""
        mock_provider = AsyncMock()
        mock_provider.provider_name = "mock"
        mock_provider.model_name = "mock-model"
        mock_provider.version = "v1"
        mock_provider.device = "cpu"
        mock_provider.score_pairs.side_effect = RuntimeError("Inference hardware unavailable")

        config = RerankerConfig(allow_fallback=True)
        service = CrossEncoderRerankingService(provider=mock_provider, config=config)

        c1 = FusedCandidate(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            organization_id=org_id,
            rrf_score=0.03,
            rank=1,
            payload={"text": "First chunk"},
        )
        c2 = FusedCandidate(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            organization_id=org_id,
            rrf_score=0.02,
            rank=2,
            payload={"text": "Second chunk"},
        )

        result = await service.rerank(
            query="test query",
            candidates=[c1, c2],
            organization_id=org_id,
            top_k=2,
        )

        # Fallback preserves original RRF order
        assert len(result.candidates) == 2
        assert result.candidates[0].chunk_id == c1.chunk_id
        assert result.candidates[1].chunk_id == c2.chunk_id
        assert result.diagnostics.is_degraded is True
        assert "Inference hardware unavailable" in (result.diagnostics.degradation_reason or "")

    @pytest.mark.asyncio
    async def test_strict_failure_when_fallback_disabled(self, org_id: uuid.UUID) -> None:
        """Verify when allow_fallback=False, provider failure raises exception."""
        mock_provider = AsyncMock()
        mock_provider.provider_name = "mock"
        mock_provider.model_name = "mock-model"
        mock_provider.version = "v1"
        mock_provider.device = "cpu"
        mock_provider.score_pairs.side_effect = RuntimeError("Fatal GPU out of memory")

        config = RerankerConfig(allow_fallback=False)
        service = CrossEncoderRerankingService(provider=mock_provider, config=config)

        c = FusedCandidate(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            organization_id=org_id,
            rrf_score=0.03,
            payload={"text": "Chunk text"},
        )
        with pytest.raises(Exception) as exc_info:
            await service.rerank(
                query="test",
                candidates=[c],
                organization_id=org_id,
            )
        assert "Fatal GPU out of memory" in str(exc_info.value)

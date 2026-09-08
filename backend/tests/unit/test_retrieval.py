"""Unit tests for dense retrieval validation, scoring, filtering, and orchestration."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.embeddings.config import EmbeddingConfig
from app.embeddings.service import EmbeddingService
from app.models.document import DocumentChunk
from app.retrieval.config import RetrievalConfig
from app.retrieval.exceptions import (
    InvalidQueryError,
    RetrievalTenantError,
    RetrievalTimeoutError,
    RetrievalValidationError,
)
from app.retrieval.filters import RetrievalFilterBuilder
from app.retrieval.scoring import ScoreProcessor
from app.retrieval.service import DenseRetrievalService
from app.retrieval.validators import FilterValidator, QueryValidator
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.models import VectorPoint, VectorSearchResult
from app.vectorstore.providers.fake import FakeVectorStoreProvider
from app.vectorstore.service import VectorStoreService


class DummyTokenizer:
    """Simulated tokenizer for unit testing token limits."""

    def __init__(self, token_multiplier: int = 1) -> None:
        self.multiplier = token_multiplier

    def count_tokens(self, text: str) -> int:
        return len(text.split()) * self.multiplier


@pytest.fixture
def retrieval_config() -> RetrievalConfig:
    return RetrievalConfig(
        default_top_k=5,
        max_top_k=20,
        min_query_characters=3,
        max_query_characters=100,
        max_query_tokens=25,
        score_threshold=0.5,
        parent_context_enabled=True,
        timeout_seconds=5.0,
    )


class TestQueryValidation:
    """Validates natural language search query guardrails."""

    def test_valid_query_cleaned_and_normalized(self, retrieval_config: RetrievalConfig) -> None:
        raw_query = "   What are Q3 financial results?   "
        cleaned, chars, tokens = QueryValidator.validate_and_clean(
            query=raw_query,
            config=retrieval_config,
        )
        assert cleaned == "What are Q3 financial results?"
        assert chars == 30
        assert tokens == 5

    def test_multilingual_unicode_support(self, retrieval_config: RetrievalConfig) -> None:
        arabic_query = "ما هي أرباح الربع الثالث؟"
        cleaned_ar, chars_ar, tokens_ar = QueryValidator.validate_and_clean(
            query=arabic_query,
            config=retrieval_config,
        )
        assert cleaned_ar == arabic_query
        assert chars_ar > 0
        assert tokens_ar == 5

        turkish_query = "Şirketin yıllık net geliri nedir?"
        cleaned_tr, chars_tr, tokens_tr = QueryValidator.validate_and_clean(
            query=turkish_query,
            config=retrieval_config,
        )
        assert cleaned_tr == turkish_query
        assert chars_tr > 0
        assert tokens_tr == 5

    def test_query_too_short_raises(self, retrieval_config: RetrievalConfig) -> None:
        with pytest.raises(InvalidQueryError) as exc_info:
            QueryValidator.validate_and_clean(query="ab", config=retrieval_config)
        assert "at least 3 characters" in exc_info.value.message

    def test_query_empty_or_whitespace_raises(self, retrieval_config: RetrievalConfig) -> None:
        with pytest.raises(InvalidQueryError):
            QueryValidator.validate_and_clean(query="   ", config=retrieval_config)

    def test_query_too_long_raises(self, retrieval_config: RetrievalConfig) -> None:
        long_query = "x" * 101
        with pytest.raises(InvalidQueryError) as exc_info:
            QueryValidator.validate_and_clean(query=long_query, config=retrieval_config)
        assert "exceeds maximum character limit" in exc_info.value.message

    def test_query_token_limit_raises(self, retrieval_config: RetrievalConfig) -> None:
        tokenizer = DummyTokenizer(token_multiplier=10)
        query = "This query has five words"
        with pytest.raises(InvalidQueryError) as exc_info:
            QueryValidator.validate_and_clean(
                query=query,
                config=retrieval_config,
                tokenizer=tokenizer,
            )
        assert "exceeds maximum token limit" in exc_info.value.message


class TestFilterValidation:
    """Validates operational filter constraints and tenant boundaries."""

    def test_missing_organization_id_raises(self, retrieval_config: RetrievalConfig) -> None:
        with pytest.raises(RetrievalTenantError):
            FilterValidator.validate(
                organization_id=None,  # type: ignore[arg-type]
                top_k=5,
                config=retrieval_config,
            )

    def test_invalid_top_k_bounds(self, retrieval_config: RetrievalConfig) -> None:
        org_id = uuid.uuid4()
        with pytest.raises(RetrievalValidationError):
            FilterValidator.validate(organization_id=org_id, top_k=0, config=retrieval_config)
        with pytest.raises(RetrievalValidationError):
            FilterValidator.validate(organization_id=org_id, top_k=25, config=retrieval_config)

    def test_invalid_page_number(self, retrieval_config: RetrievalConfig) -> None:
        org_id = uuid.uuid4()
        with pytest.raises(RetrievalValidationError):
            FilterValidator.validate(
                organization_id=org_id,
                top_k=5,
                config=retrieval_config,
                page_number=0,
            )

    def test_invalid_chunk_type(self, retrieval_config: RetrievalConfig) -> None:
        org_id = uuid.uuid4()
        with pytest.raises(RetrievalValidationError) as exc_info:
            FilterValidator.validate(
                organization_id=org_id,
                top_k=5,
                config=retrieval_config,
                chunk_type="non_existent_type",
            )
        assert "Invalid chunk_type" in exc_info.value.message

    def test_invalid_score_threshold(self, retrieval_config: RetrievalConfig) -> None:
        org_id = uuid.uuid4()
        with pytest.raises(RetrievalValidationError):
            FilterValidator.validate(
                organization_id=org_id,
                top_k=5,
                config=retrieval_config,
                score_threshold=float("nan"),
            )


class TestScoringAndFiltering:
    """Verifies score thresholding and preservation of raw scores."""

    def test_score_threshold_filtering(self) -> None:
        candidates = [
            VectorSearchResult(id=uuid.uuid4(), score=0.85, payload={}),
            VectorSearchResult(id=uuid.uuid4(), score=0.45, payload={}),
            VectorSearchResult(id=uuid.uuid4(), score=0.92, payload={}),
            VectorSearchResult(id=uuid.uuid4(), score=0.30, payload={}),
        ]
        filtered = ScoreProcessor.filter_and_sort(candidates=candidates, score_threshold=0.5)
        assert len(filtered) == 2
        assert filtered[0].score == 0.92
        assert filtered[1].score == 0.85

    def test_preserves_raw_scores_without_artificial_normalization(self) -> None:
        candidates = [
            VectorSearchResult(id=uuid.uuid4(), score=-0.25, payload={}),
            VectorSearchResult(id=uuid.uuid4(), score=0.0, payload={}),
            VectorSearchResult(id=uuid.uuid4(), score=1.85, payload={}),
        ]
        filtered = ScoreProcessor.filter_and_sort(candidates=candidates, score_threshold=None)
        assert len(filtered) == 3
        # Strict equality verifying no transformation/clamping occurred
        assert filtered[0].score == 1.85
        assert filtered[1].score == 0.0
        assert filtered[2].score == -0.25

    def test_retrieval_filter_builder_includes_organization(self) -> None:
        org_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        q_filter = RetrievalFilterBuilder.build_vector_filter(
            organization_id=org_id,
            document_id=doc_id,
            chunk_type="table",
            page_number=3,
            section="Executive Summary",
        )
        must_keys = [c.key for c in q_filter.must]
        assert "organization_id" in must_keys
        assert "document_id" in must_keys
        assert "chunk_type" in must_keys
        assert "page_number" in must_keys
        assert "section" in must_keys


class TestDenseRetrievalService:
    """Unit tests for the orchestration service with fake providers."""

    @pytest.mark.asyncio
    async def test_search_pipeline_end_to_end_mocked(
        self, retrieval_config: RetrievalConfig
    ) -> None:
        org_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        parent_id = uuid.uuid4()

        # 1. Setup Local Embedding Service
        from dataclasses import replace

        from app.embeddings.providers.factory import EmbeddingProviderFactory

        base_emb = EmbeddingConfig.from_settings()
        emb_config = replace(base_emb, provider="local", model="local-hash", dimensions=8)
        emb_provider = EmbeddingProviderFactory.create(emb_config)
        emb_service = EmbeddingService(config=emb_config, provider=emb_provider)

        # 2. Setup Fake Vector Store Service
        vs_config = VectorStoreConfig(
            collection_prefix="test",
            distance="cosine",
        )
        vs_provider = FakeVectorStoreProvider()
        vs_service = VectorStoreService(config=vs_config, provider=vs_provider)

        collection_name = vs_service.resolve_collection_name(
            embedding_provider=emb_service.provider_name,
            embedding_model=emb_service.model_name,
            dimensions=emb_service.dimensions,
            version=emb_service.version,
        )
        await vs_provider.ensure_collection(collection_name, 8, "cosine")

        # Ingest a point into fake vector store matching the query
        target_vec = await emb_service.embed_query("operating profit increase")
        point = VectorPoint(
            id=chunk_id,
            vector=target_vec,
            payload={
                "organization_id": str(org_id),
                "document_id": str(doc_id),
                "chunk_id": str(chunk_id),
                "parent_chunk_id": str(parent_id),
                "text": "Quarterly operating profit increased by 15%.",
                "chunk_index": 1,
                "chunk_type": "text",
                "token_count": 8,
                "character_count": 44,
                "page_number": 2,
                "section": "Financial Results",
            },
        )
        await vs_provider.upsert(collection_name, [point])

        # 3. Setup Mock Chunk Repository
        mock_repo = MagicMock()
        child_chunk = DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            organization_id=org_id,
            content="Quarterly operating profit increased by 15%.",
            chunk_index=1,
            chunk_type="text",
            token_count=8,
            character_count=44,
            parent_chunk_id=parent_id,
        )
        parent_chunk = DocumentChunk(
            id=parent_id,
            document_id=doc_id,
            organization_id=org_id,
            content="Financial Highlights Section: Comprehensive review.",
            chunk_index=0,
            chunk_type="parent",
            token_count=10,
            character_count=52,
        )

        async def fake_get_by_ids(
            session: Any,
            ids: Any,
            organization_id: Any,
        ) -> list[DocumentChunk]:
            found = []
            for i in ids:
                if i == chunk_id:
                    found.append(child_chunk)
                elif i == parent_id:
                    found.append(parent_chunk)
            return found

        mock_repo.get_by_ids = AsyncMock(side_effect=fake_get_by_ids)
        mock_session = AsyncMock()

        # 4. Execute Dense Retrieval Service
        retrieval_svc = DenseRetrievalService(
            embedding_service=emb_service,
            vector_store_service=vs_service,
            chunk_repository=mock_repo,
            config=retrieval_config,
        )

        result = await retrieval_svc.search(
            session=mock_session,
            organization_id=org_id,
            query="operating profit increase",
            top_k=5,
            include_parent=True,
            score_threshold=0.1,
        )

        assert result.query == "operating profit increase"
        assert len(result.chunks) == 1
        chunk_res = result.chunks[0]
        assert chunk_res.chunk_id == chunk_id
        assert chunk_res.parent_chunk_id == parent_id
        assert chunk_res.parent_text == "Financial Highlights Section: Comprehensive review."
        assert chunk_res.section == "Financial Results"
        assert chunk_res.score > 0.0

        # Verify diagnostics
        diag = result.diagnostics
        assert diag.total_candidates_found == 1
        assert diag.returned_chunks_count == 1
        assert diag.dimensions == 8
        assert diag.embedding_latency_ms >= 0.0
        assert diag.vector_search_latency_ms >= 0.0
        assert diag.hydration_latency_ms >= 0.0
        assert diag.total_latency_ms >= 0.0

    @pytest.mark.asyncio
    async def test_search_timeout_raises(self, retrieval_config: RetrievalConfig) -> None:
        emb_service = MagicMock()
        vs_service = MagicMock()

        async def slow_embed(query: str) -> list[float]:
            import asyncio

            await asyncio.sleep(0.5)
            return [0.1] * 8

        emb_service.provider = None
        emb_service.embed_query = AsyncMock(side_effect=slow_embed)
        retrieval_svc = DenseRetrievalService(
            embedding_service=emb_service,
            vector_store_service=vs_service,
            config=RetrievalConfig(timeout_seconds=0.05),
        )

        with pytest.raises(RetrievalTimeoutError) as exc_info:
            await retrieval_svc.search(
                session=AsyncMock(),
                organization_id=uuid.uuid4(),
                query="valid test query",
            )
        assert "exceeded timeout limit" in exc_info.value.message

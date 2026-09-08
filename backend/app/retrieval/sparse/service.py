"""Domain service executing sparse lexical retrieval using BM25."""

import logging
import time
import uuid

from app.core.config import get_settings
from app.embeddings.service import EmbeddingService
from app.retrieval.config import BM25Config, RetrievalConfig, get_retrieval_config
from app.retrieval.exceptions import VectorSearchError
from app.retrieval.filters import RetrievalFilterBuilder
from app.retrieval.sparse.analyzer import MultilingualSparseAnalyzer
from app.retrieval.sparse.bm25 import BM25Encoder
from app.retrieval.sparse.models import SparseRetrievalResult
from app.retrieval.sparse.stats import (
    TenantCorpusStatsManager,
    get_tenant_corpus_stats_manager,
)
from app.vectorstore.service import VectorStoreService

logger = logging.getLogger(__name__)


class SparseRetrievalService:
    """Enterprise domain service executing sparse lexical BM25 retrieval.

    Pipeline:
    1. Multilingual query tokenization and normalization (Arabic, Turkish, English, numbers).
    2. Tenant-scoped IDF calculation and query sparse vector generation.
    3. Metadata and tenant filter construction.
    4. Sparse vector search against vector store (Qdrant sparse index).
    5. Scoring, rank tracking, and latency diagnostics assembly.
    """

    def __init__(
        self,
        vector_store_service: VectorStoreService,
        embedding_service: EmbeddingService | None = None,
        analyzer: MultilingualSparseAnalyzer | None = None,
        bm25_encoder: BM25Encoder | None = None,
        stats_manager: TenantCorpusStatsManager | None = None,
        config: RetrievalConfig | None = None,
        bm25_config: BM25Config | None = None,
    ) -> None:
        self.vector_store_service = vector_store_service
        self.embedding_service = embedding_service
        self.bm25_config = bm25_config or BM25Config()
        self.analyzer = analyzer or MultilingualSparseAnalyzer(self.bm25_config)
        self.stats_manager = stats_manager or get_tenant_corpus_stats_manager()
        self.bm25_encoder = bm25_encoder or BM25Encoder(
            config=self.bm25_config,
            stats_manager=self.stats_manager,
        )
        self.config = config or get_retrieval_config()

    def _resolve_collection_name(self) -> str:
        """Derive the deterministic collection name matching active embedding identity."""
        if self.embedding_service is not None:
            provider_name = self.embedding_service.provider_name
            model_name = self.embedding_service.model_name
            dimensions = self.embedding_service.dimensions
            version = self.embedding_service.version
        else:
            settings = get_settings()

            provider_name = settings.EMBEDDING_PROVIDER
            model_name = settings.EMBEDDING_MODEL
            dimensions = settings.EMBEDDING_DIMENSIONS
            version = settings.EMBEDDING_VERSION

        return self.vector_store_service.get_collection_name(
            embedding_provider=provider_name,
            embedding_model=model_name,
            dimensions=dimensions,
            version=version,
        )

    async def search(
        self,
        organization_id: uuid.UUID,
        query: str,
        *,
        top_k: int | None = None,
        document_id: uuid.UUID | None = None,
        chunk_type: str | None = None,
        page_number: int | None = None,
        section: str | None = None,
        score_threshold: float | None = None,
    ) -> SparseRetrievalResult:
        """Execute sparse lexical search strictly scoped to tenant boundaries."""
        t_start = time.perf_counter()
        effective_top_k = min(
            top_k or self.config.default_top_k,
            self.config.max_top_k,
        )

        # 1. Analyze and tokenize query
        analyzed = self.analyzer.analyze(query)
        if not analyzed.tokens or not analyzed.term_frequencies:
            logger.info("Sparse query '%s' yielded zero lexical tokens.", query[:50])
            empty_sparse = self.bm25_encoder.encode_query(analyzed, organization_id)
            return SparseRetrievalResult(
                query=query,
                sparse_vector=empty_sparse,
                analyzed_tokens=[],
                candidates=[],
                latency_ms=(time.perf_counter() - t_start) * 1000.0,
            )

        # 2. Encode query into IDF-weighted sparse vector
        query_sparse = self.bm25_encoder.encode_query(analyzed, organization_id)

        # 3. Build tenant and metadata filters
        filter_conditions = RetrievalFilterBuilder.build_metadata_filter(
            organization_id=organization_id,
            document_id=document_id,
            chunk_type=chunk_type,
            page_number=page_number,
            section=section,
        )

        collection_name = self._resolve_collection_name()

        # 4. Execute sparse vector search against vector engine
        try:
            candidates = await self.vector_store_service.search_sparse_vectors(
                collection_name=collection_name,
                organization_id=organization_id,
                sparse_vector=query_sparse,
                limit=effective_top_k,
                score_threshold=score_threshold,
                filter_conditions=filter_conditions,
            )
        except Exception as exc:
            logger.error(
                "Sparse vector search failed on collection '%s': %s",
                collection_name,
                exc,
            )
            raise VectorSearchError(
                f"Sparse vector search failed on collection '{collection_name}': {exc}"
            ) from exc

        t_end = time.perf_counter()
        latency_ms = round((t_end - t_start) * 1000.0, 3)

        return SparseRetrievalResult(
            query=query,
            sparse_vector=query_sparse,
            analyzed_tokens=analyzed.tokens,
            candidates=candidates,
            latency_ms=latency_ms,
        )

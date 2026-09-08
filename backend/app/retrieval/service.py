"""Domain service orchestrating basic dense vector retrieval."""

import asyncio
import logging
import time
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings.service import EmbeddingService
from app.models.document import DocumentChunk
from app.repositories.chunk import DocumentChunkRepository
from app.retrieval.config import RetrievalConfig, get_retrieval_config
from app.retrieval.exceptions import (
    RetrievalError,
    RetrievalTimeoutError,
    VectorSearchError,
)
from app.retrieval.filters import RetrievalFilterBuilder
from app.retrieval.models import (
    DenseRetrievalResult,
    RetrievalDiagnostics,
    RetrievedChunk,
)
from app.retrieval.scoring import ScoreProcessor
from app.retrieval.validators import FilterValidator, QueryValidator
from app.vectorstore.models import VectorSearchResult
from app.vectorstore.service import VectorStoreService

logger = logging.getLogger(__name__)


class DenseRetrievalService:
    """Enterprise domain service executing semantic dense retrieval.

    Retrieval Pipeline:
    1. Query Validation & Normalization (NFC, character/token bounds).
    2. Operational Filter Validation & Tenant Isolation Guardrails.
    3. Query Embedding Generation via active Task 10 embedding provider.
    4. Dense Vector Similarity Search against Qdrant Vector Store (Task 11).
    5. Score Handling & Threshold Filtering (preserving raw engine scores).
    6. Batch Chunk & Parent Context Hydration (strictly 0 N+1 queries).
    7. Diagnostics & Latency Breakdown Assembly.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store_service: VectorStoreService,
        chunk_repository: DocumentChunkRepository | None = None,
        config: RetrievalConfig | None = None,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_store_service = vector_store_service
        self.chunk_repository = chunk_repository or DocumentChunkRepository()
        self.config = config or get_retrieval_config()

    async def search(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        query: str,
        *,
        top_k: int | None = None,
        document_id: uuid.UUID | None = None,
        chunk_type: str | None = None,
        page_number: int | None = None,
        section: str | None = None,
        score_threshold: float | None = None,
        include_parent: bool | None = None,
    ) -> DenseRetrievalResult:
        """Execute end-to-end dense retrieval under tenant isolation."""
        t0 = time.perf_counter()

        target_top_k = top_k if top_k is not None else self.config.default_top_k
        target_score_threshold = (
            score_threshold if score_threshold is not None else self.config.score_threshold
        )
        should_include_parent = (
            include_parent if include_parent is not None else self.config.parent_context_enabled
        )

        try:
            return await asyncio.wait_for(
                self._execute_search_pipeline(
                    session=session,
                    organization_id=organization_id,
                    query=query,
                    top_k=target_top_k,
                    document_id=document_id,
                    chunk_type=chunk_type,
                    page_number=page_number,
                    section=section,
                    score_threshold=target_score_threshold,
                    include_parent=should_include_parent,
                    start_time=t0,
                ),
                timeout=self.config.timeout_seconds,
            )
        except TimeoutError as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.error(
                "Dense retrieval timed out after %.2fms (limit: %.2fs)",
                elapsed_ms,
                self.config.timeout_seconds,
            )
            raise RetrievalTimeoutError(
                f"Retrieval operation exceeded timeout limit of {self.config.timeout_seconds}s.",
                details={"timeout_seconds": self.config.timeout_seconds, "elapsed_ms": elapsed_ms},
            ) from exc

    async def retrieve_candidates(
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
    ) -> tuple[list[VectorSearchResult], float, str, int, int, float, float, str]:
        """Validate, embed query, and retrieve scored vector candidates from vector store.

        Returns:
            Tuple of (candidates, total_dense_latency_ms, collection_name, char_count,
                      token_count, embedding_latency_ms, vector_search_latency_ms, cleaned_query).
        """
        t0 = time.perf_counter()
        effective_top_k = top_k if top_k is not None else self.config.default_top_k

        # 1. Validation
        tokenizer = getattr(self.embedding_service.provider, "tokenizer", None)
        cleaned_query, char_count, token_count = QueryValidator.validate_and_clean(
            query=query,
            config=self.config,
            tokenizer=tokenizer,
        )

        FilterValidator.validate(
            organization_id=organization_id,
            top_k=effective_top_k,
            config=self.config,
            chunk_type=chunk_type,
            page_number=page_number,
            score_threshold=score_threshold,
        )

        # 2. Query Embedding Phase
        t_emb0 = time.perf_counter()
        try:
            query_vector = await self.embedding_service.embed_query(cleaned_query)
        except Exception as exc:
            logger.error("Failed to generate query embedding: %s", exc)
            raise RetrievalError(f"Failed to generate query embedding: {exc}") from exc
        embedding_latency_ms = (time.perf_counter() - t_emb0) * 1000.0

        # 3. Vector Similarity Search Phase
        t_search0 = time.perf_counter()
        collection_name = self.vector_store_service.resolve_collection_name(
            embedding_provider=self.embedding_service.provider_name,
            embedding_model=self.embedding_service.model_name,
            dimensions=self.embedding_service.dimensions,
            version=self.embedding_service.version,
        )

        vector_filter = RetrievalFilterBuilder.build_vector_filter(
            organization_id=organization_id,
            document_id=document_id,
            chunk_type=chunk_type,
            page_number=page_number,
            section=section,
        )

        try:
            raw_candidates = await self.vector_store_service.search_vectors(
                collection_name=collection_name,
                organization_id=organization_id,
                vector=query_vector,
                limit=effective_top_k,
                score_threshold=score_threshold,
                filter_conditions=vector_filter,
            )
        except Exception as exc:
            logger.error("Vector search failed on collection '%s': %s", collection_name, exc)
            raise VectorSearchError(f"Vector search failed: {exc}") from exc

        candidates = ScoreProcessor.filter_and_sort(
            candidates=raw_candidates,
            score_threshold=score_threshold,
        )
        vector_search_latency_ms = (time.perf_counter() - t_search0) * 1000.0
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return (
            candidates,
            latency_ms,
            collection_name,
            char_count,
            token_count,
            embedding_latency_ms,
            vector_search_latency_ms,
            cleaned_query,
        )

    async def _execute_search_pipeline(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        query: str,
        top_k: int,
        document_id: uuid.UUID | None,
        chunk_type: str | None,
        page_number: int | None,
        section: str | None,
        score_threshold: float | None,
        include_parent: bool,
        start_time: float,
    ) -> DenseRetrievalResult:
        """Internal search execution pipeline."""
        (
            candidates,
            dense_latency_ms,
            collection_name,
            char_count,
            token_count,
            embedding_latency_ms,
            vector_search_latency_ms,
            cleaned_query,
        ) = await self.retrieve_candidates(
            organization_id=organization_id,
            query=query,
            top_k=top_k,
            document_id=document_id,
            chunk_type=chunk_type,
            page_number=page_number,
            section=section,
            score_threshold=score_threshold,
        )

        # 4. Batch Hydration Phase (Zero N+1 Queries)
        t_hyd0 = time.perf_counter()
        retrieved_chunks = await self._hydrate_results(
            session=session,
            organization_id=organization_id,
            candidates=candidates,
            include_parent=include_parent,
        )
        hydration_latency_ms = (time.perf_counter() - t_hyd0) * 1000

        total_latency_ms = (time.perf_counter() - start_time) * 1000

        diagnostics = RetrievalDiagnostics(
            collection_name=collection_name,
            embedding_provider=self.embedding_service.provider_name,
            embedding_model=self.embedding_service.model_name,
            dimensions=self.embedding_service.dimensions,
            query_character_count=char_count,
            query_token_count=token_count,
            total_candidates_found=len(candidates),
            returned_chunks_count=len(retrieved_chunks),
            score_threshold=score_threshold,
            embedding_latency_ms=embedding_latency_ms,
            vector_search_latency_ms=vector_search_latency_ms,
            hydration_latency_ms=hydration_latency_ms,
            total_latency_ms=total_latency_ms,
        )

        return DenseRetrievalResult(
            query=cleaned_query,
            chunks=retrieved_chunks,
            diagnostics=diagnostics,
        )

    async def _hydrate_results(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        candidates: Sequence[VectorSearchResult],
        include_parent: bool,
    ) -> list[RetrievedChunk]:
        """Hydrate matched chunks from PostgreSQL with zero N+1 queries."""
        if not candidates:
            return []

        # VectorSearchResult point id corresponds to chunk_id (or vector_point_id)
        # In Task 11 indexing: point.id is uuid5(NAMESPACE_URL, f"{chunk_id}_{embedding_id}")
        # AND payload["chunk_id"] stores the actual DocumentChunk.id
        chunk_ids: list[uuid.UUID] = []
        for cand in candidates:
            raw_cid = cand.payload.get("chunk_id")
            if raw_cid:
                try:
                    chunk_ids.append(uuid.UUID(str(raw_cid)))
                except ValueError:
                    chunk_ids.append(cand.id)
            else:
                chunk_ids.append(cand.id)

        # Batch fetch all matched chunks in a single SQL query
        db_chunks = await self.chunk_repository.get_by_ids(
            session=session,
            ids=chunk_ids,
            organization_id=organization_id,
        )
        chunks_by_id: dict[uuid.UUID, DocumentChunk] = {c.id: c for c in db_chunks}

        # Batch fetch parent chunks if requested (second single query)
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

        # Enrich and build RetrievedChunk keeping original candidate order
        retrieved: list[RetrievedChunk] = []
        for cand in candidates:
            raw_cid = cand.payload.get("chunk_id")
            cid = uuid.UUID(str(raw_cid)) if raw_cid else cand.id
            db_chunk = chunks_by_id.get(cid)
            payload = cand.payload

            # Prefer DB attributes if available, fall back to vector store payload
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

            parent_id = (
                db_chunk.parent_chunk_id
                if db_chunk
                else (
                    uuid.UUID(str(payload["parent_chunk_id"]))
                    if payload.get("parent_chunk_id")
                    else None
                )
            )
            parent_text = (
                parents_by_id[parent_id].content
                if (parent_id and parent_id in parents_by_id)
                else None
            )

            # Parse document_id and organization_id safely
            doc_id_str = str(
                payload.get("document_id") or (db_chunk.document_id if db_chunk else uuid.uuid4())
            )
            org_id_str = str(payload.get("organization_id") or organization_id)

            retrieved.append(
                RetrievedChunk(
                    chunk_id=cid,
                    document_id=uuid.UUID(doc_id_str),
                    organization_id=uuid.UUID(org_id_str),
                    score=cand.score,  # Raw score preserved
                    text=text,
                    chunk_index=chunk_index,
                    chunk_type=chunk_type,
                    token_count=token_count,
                    character_count=char_count,
                    page_number=page_number,
                    page_end=page_end,
                    section=section,
                    heading_hierarchy=list(payload.get("heading_hierarchy") or []),
                    parent_chunk_id=parent_id,
                    parent_text=parent_text,
                    metadata=dict(payload.get("metadata") or {}),
                )
            )

        return retrieved

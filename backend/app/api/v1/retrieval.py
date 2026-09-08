"""REST API endpoints for dense vector retrieval."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AppException,
    BadRequestAppException,
    ForbiddenAppException,
    ValidationAppException,
)
from app.db.postgres import get_db_session
from app.db.qdrant import create_qdrant_client
from app.rbac.catalog import PERM_DOCUMENTS_READ
from app.retrieval.config import get_retrieval_config
from app.retrieval.exceptions import (
    InvalidQueryError,
    RetrievalError,
    RetrievalTenantError,
    RetrievalTimeoutError,
    RetrievalValidationError,
    VectorSearchError,
)
from app.retrieval.hybrid.service import HybridRetrievalService
from app.retrieval.schemas import (
    DenseRetrievalRequest,
    DenseRetrievalResponse,
    HybridDiagnosticsResponse,
    HybridLatencyBreakdown,
    HybridRetrievalRequest,
    HybridRetrievalResponse,
    HybridRetrievedChunkResponse,
    RetrievalDiagnosticsResponse,
    RetrievalLatencyBreakdown,
    RetrievedChunkResponse,
)
from app.retrieval.service import DenseRetrievalService
from app.schemas.common import ErrorResponse
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.providers.qdrant import QdrantVectorStoreProvider
from app.vectorstore.service import VectorStoreService

router = APIRouter(prefix="/retrieval", tags=["Retrieval"])


def get_dense_retrieval_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DenseRetrievalService:
    """Dependency producing or resolving the DenseRetrievalService instance."""
    existing = getattr(request.app.state, "dense_retrieval_service", None)
    if existing is not None and isinstance(existing, DenseRetrievalService):
        return existing

    # Fallback initialization if not pre-populated in app.state
    vs_service = getattr(request.app.state, "vector_store_service", None)
    if vs_service is None:
        vs_config = VectorStoreConfig.from_settings(settings)
        qdrant_client = getattr(request.app.state, "qdrant_client", None)
        if qdrant_client is None:
            qdrant_client = create_qdrant_client(settings)
        provider = QdrantVectorStoreProvider(client=qdrant_client, config=vs_config)
        vs_service = VectorStoreService(config=vs_config, provider=provider)

    emb_service = getattr(request.app.state, "embedding_service", None)
    if emb_service is None:
        from app.services.embedding_pipeline import create_default_embedding_service

        redis_cli = getattr(request.app.state, "redis_client", None)
        emb_service = create_default_embedding_service(settings=settings, redis_client=redis_cli)
        request.app.state.embedding_service = emb_service

    retrieval_config = get_retrieval_config()
    service = DenseRetrievalService(
        embedding_service=emb_service,
        vector_store_service=vs_service,
        config=retrieval_config,
    )
    request.app.state.dense_retrieval_service = service
    return service


@router.post(
    "/search",
    response_model=DenseRetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Dense Vector Search",
    description=(
        "Execute semantic dense retrieval over document chunks strictly scoped "
        "to the caller's organization. Supports document, chunk type, page, and "
        "score threshold filters with optional parent context hydration."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Dense retrieval completed successfully"},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Invalid query"},
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Tenant permission denied",
        },
        getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422): {
            "model": ErrorResponse,
            "description": "Validation error in parameters",
        },
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse, "description": "Vector store error"},
        status.HTTP_504_GATEWAY_TIMEOUT: {
            "model": ErrorResponse,
            "description": "Retrieval timeout",
        },
    },
)
async def dense_search(
    request_data: DenseRetrievalRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DenseRetrievalService, Depends(get_dense_retrieval_service)],
) -> DenseRetrievalResponse:
    """Execute tenant-isolated dense semantic search with metadata filters and parent hydration."""
    try:
        result = await service.search(
            session=session,
            organization_id=tenant.organization_id,
            query=request_data.query,
            top_k=request_data.top_k,
            document_id=request_data.document_id,
            chunk_type=request_data.chunk_type,
            page_number=request_data.page_number,
            section=request_data.section,
            score_threshold=request_data.score_threshold,
            include_parent=request_data.include_parent,
        )
    except InvalidQueryError as exc:
        raise BadRequestAppException(message=exc.message, details=exc.details) from exc
    except RetrievalValidationError as exc:
        raise ValidationAppException(message=exc.message, details=exc.details) from exc
    except RetrievalTenantError as exc:
        raise ForbiddenAppException(message=exc.message, details=exc.details) from exc
    except RetrievalTimeoutError as exc:
        raise AppException(
            message=exc.message,
            code="GATEWAY_TIMEOUT",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            details=exc.details,
        ) from exc
    except VectorSearchError as exc:
        raise AppException(
            message=exc.message,
            code="BAD_GATEWAY",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=exc.details,
        ) from exc
    except RetrievalError as exc:
        raise AppException(
            message=exc.message,
            code="RETRIEVAL_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=exc.details,
        ) from exc

    chunk_responses = [
        RetrievedChunkResponse(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            score=c.score,
            text=c.text,
            chunk_index=c.chunk_index,
            chunk_type=c.chunk_type,
            token_count=c.token_count,
            character_count=c.character_count,
            page_number=c.page_number,
            page_end=c.page_end,
            section=c.section,
            heading_hierarchy=c.heading_hierarchy,
            parent_chunk_id=c.parent_chunk_id,
            parent_text=c.parent_text,
            metadata=c.metadata,
        )
        for c in result.chunks
    ]

    diag = result.diagnostics
    latency = RetrievalLatencyBreakdown(
        embedding_ms=diag.embedding_latency_ms,
        vector_search_ms=diag.vector_search_latency_ms,
        hydration_ms=diag.hydration_latency_ms,
        total_ms=diag.total_latency_ms,
    )
    diagnostics_response = RetrievalDiagnosticsResponse(
        collection_name=diag.collection_name,
        embedding_provider=diag.embedding_provider,
        embedding_model=diag.embedding_model,
        dimensions=diag.dimensions,
        query_character_count=diag.query_character_count,
        query_token_count=diag.query_token_count,
        total_candidates_found=diag.total_candidates_found,
        returned_chunks_count=diag.returned_chunks_count,
        score_threshold=diag.score_threshold,
        latency=latency,
    )

    return DenseRetrievalResponse(
        query=result.query,
        total_results=len(chunk_responses),
        results=chunk_responses,
        diagnostics=diagnostics_response,
    )


def get_hybrid_retrieval_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    dense_service: Annotated[DenseRetrievalService, Depends(get_dense_retrieval_service)],
) -> "HybridRetrievalService":
    """Dependency producing or resolving the HybridRetrievalService instance."""
    from app.retrieval.config import get_hybrid_retrieval_config
    from app.retrieval.hybrid.service import HybridRetrievalService
    from app.retrieval.sparse.service import SparseRetrievalService

    existing = getattr(request.app.state, "hybrid_retrieval_service", None)
    if existing is not None and isinstance(existing, HybridRetrievalService):
        return existing

    sparse_service = getattr(request.app.state, "sparse_retrieval_service", None)
    if sparse_service is None:
        sparse_service = SparseRetrievalService(
            vector_store_service=dense_service.vector_store_service,
            embedding_service=dense_service.embedding_service,
        )
        request.app.state.sparse_retrieval_service = sparse_service

    reranker_service = getattr(request.app.state, "reranker_service", None)
    if reranker_service is None and settings.RERANKING_ENABLED:
        from app.reranking.config import get_reranker_config
        from app.reranking.service import CrossEncoderRerankingService

        reranker_service = CrossEncoderRerankingService(config=get_reranker_config())
        request.app.state.reranker_service = reranker_service

    qu_service = getattr(request.app.state, "query_understanding_service", None)
    if qu_service is None and settings.QUERY_UNDERSTANDING_ENABLED:
        from app.query.config import get_query_understanding_config
        from app.query.service import QueryUnderstandingService

        qu_service = QueryUnderstandingService(config=get_query_understanding_config())
        request.app.state.query_understanding_service = qu_service

    mq_service = getattr(request.app.state, "multi_query_service", None)

    hybrid_config = get_hybrid_retrieval_config()
    service = HybridRetrievalService(
        dense_service=dense_service,
        sparse_service=sparse_service,
        chunk_repository=dense_service.chunk_repository,
        config=hybrid_config,
        reranker_service=reranker_service,
        query_understanding_service=qu_service,
        multi_query_service=mq_service,
    )
    if mq_service is None and qu_service is not None:
        from app.query.multi_retrieval import MultiQueryRetrievalService

        service.multi_query_service = MultiQueryRetrievalService(
            hybrid_service=service,
            reranker_service=reranker_service,
            chunk_repository=dense_service.chunk_repository,
        )
        request.app.state.multi_query_service = service.multi_query_service

    request.app.state.hybrid_retrieval_service = service
    return service


@router.post(
    "/hybrid-search",
    response_model=HybridRetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid Retrieval with Reciprocal Rank Fusion",
    description=(
        "Execute advanced hybrid retrieval combining dense semantic similarity "
        "and sparse BM25 lexical search with Reciprocal Rank Fusion (RRF). "
        "Strictly isolated by organization tenant boundaries with zero N+1 parent hydration."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Hybrid retrieval completed successfully"},
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid query or feature disabled",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Tenant permission denied",
        },
        getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422): {
            "model": ErrorResponse,
            "description": "Validation error in parameters",
        },
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse, "description": "Vector store error"},
        status.HTTP_504_GATEWAY_TIMEOUT: {
            "model": ErrorResponse,
            "description": "Retrieval timeout",
        },
    },
)
async def hybrid_search(
    request_data: HybridRetrievalRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[HybridRetrievalService, Depends(get_hybrid_retrieval_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HybridRetrievalResponse:
    """Execute tenant-isolated hybrid retrieval with RRF fusion, filters, and diagnostics."""

    if not settings.HYBRID_RETRIEVAL_ENABLED:
        raise BadRequestAppException(
            message="Hybrid retrieval is currently disabled by system configuration.",
            code="HYBRID_DISABLED",
        )

    try:
        result = await service.search(
            session=session,
            organization_id=tenant.organization_id,
            query=request_data.query,
            top_k=request_data.top_k,
            dense_candidate_k=request_data.dense_candidate_k,
            sparse_candidate_k=request_data.sparse_candidate_k,
            rrf_k=request_data.rrf_k,
            document_id=request_data.document_id,
            chunk_type=request_data.chunk_type,
            page_number=request_data.page_number,
            section=request_data.section,
            score_threshold=request_data.score_threshold,
            rerank=request_data.rerank,
            rerank_candidates=request_data.rerank_candidates,
            include_parent=request_data.include_parent,
            enable_query_understanding=request_data.enable_query_understanding,
            enable_query_rewrite=request_data.enable_query_rewrite,
            enable_query_expansion=request_data.enable_query_expansion,
            enable_query_decomposition=request_data.enable_query_decomposition,
        )
    except InvalidQueryError as exc:
        raise BadRequestAppException(message=exc.message, details=exc.details) from exc
    except RetrievalValidationError as exc:
        raise ValidationAppException(message=exc.message, details=exc.details) from exc
    except RetrievalTenantError as exc:
        raise ForbiddenAppException(message=exc.message, details=exc.details) from exc
    except RetrievalTimeoutError as exc:
        raise AppException(
            message=exc.message,
            code="GATEWAY_TIMEOUT",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            details=exc.details,
        ) from exc
    except VectorSearchError as exc:
        raise AppException(
            message=exc.message,
            code="BAD_GATEWAY",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=exc.details,
        ) from exc
    except RetrievalError as exc:
        raise AppException(
            message=exc.message,
            code="RETRIEVAL_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=exc.details,
        ) from exc

    chunk_responses = [
        HybridRetrievedChunkResponse(
            rank=c.rerank_rank or (idx + 1),
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            score=c.score,
            rrf_score=c.rrf_score,
            dense_score=c.dense_score,
            dense_rank=c.dense_rank,
            sparse_score=c.sparse_score,
            sparse_rank=c.sparse_rank,
            rerank_score=c.rerank_score,
            rerank_rank=c.rerank_rank,
            original_rank=c.original_rank,
            text=c.text,
            chunk_index=c.chunk_index,
            chunk_type=c.chunk_type,
            token_count=c.token_count,
            character_count=c.character_count,
            page_number=c.page_number,
            page_end=c.page_end,
            section=c.section,
            heading_hierarchy=c.heading_hierarchy,
            parent_chunk_id=c.parent_chunk_id,
            parent_text=c.parent_text,
            metadata=c.metadata,
        )
        for idx, c in enumerate(result.chunks)
    ]

    diag = result.diagnostics
    latency = HybridLatencyBreakdown(
        dense_ms=diag.latency.dense_ms,
        sparse_ms=diag.latency.sparse_ms,
        fusion_ms=diag.latency.fusion_ms,
        rerank_ms=diag.latency.rerank_ms,
        hydration_ms=diag.latency.hydration_ms,
        total_ms=diag.latency.total_ms,
    )
    diagnostics_response = HybridDiagnosticsResponse(
        collection_name=diag.collection_name,
        dense_candidate_count=diag.dense_candidate_count,
        sparse_candidate_count=diag.sparse_candidate_count,
        merged_candidate_count=diag.merged_candidate_count,
        final_result_count=diag.final_result_count,
        rrf_k=diag.rrf_k,
        dense_candidate_k=diag.dense_candidate_k,
        sparse_candidate_k=diag.sparse_candidate_k,
        final_top_k=diag.final_top_k,
        reranking_enabled=diag.reranking_enabled,
        reranker_provider=diag.reranker_provider,
        reranker_model=diag.reranker_model,
        reranker_version=diag.reranker_version,
        reranker_candidate_count=diag.reranker_candidate_count,
        is_degraded=diag.is_degraded,
        degradation_reason=diag.degradation_reason,
        latency=latency,
    )

    return HybridRetrievalResponse(
        query=result.query,
        retrieval_mode=result.retrieval_mode,
        total_results=len(chunk_responses),
        results=chunk_responses,
        diagnostics=diagnostics_response,
    )

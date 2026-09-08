"""REST router for enterprise document storage and management."""

import contextlib
import urllib.parse
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundAppException
from app.db.postgres import get_db_session
from app.ingestion.models import ParsedDocument
from app.ingestion.service import IngestionService
from app.rbac.catalog import (
    PERM_DOCUMENTS_DELETE,
    PERM_DOCUMENTS_READ,
    PERM_DOCUMENTS_WRITE,
)
from app.schemas.chunk import (
    ChunkQualitySummaryResponse,
    DocumentChunkListResponse,
    DocumentChunkResponse,
)
from app.schemas.common import ErrorResponse
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.schemas.embedding import (
    DocumentChunkEmbeddingListResponse,
    DocumentChunkEmbeddingResponse,
    DocumentEmbeddingSummaryResponse,
    DocumentEmbeddingTriggerRequest,
)
from app.services.chunking import DocumentChunkService
from app.services.document import DocumentService
from app.services.embedding_pipeline import DocumentEmbeddingPipelineService
from app.services.vector_indexing import DocumentVectorIndexingService
from app.storage import StorageProvider, get_storage_provider, sanitize_filename
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import require_tenant_permission
from app.vectorstore.schemas import DocumentIndexingResponse, DocumentIndexingStatusResponse
from app.workers.chunking import run_chunking_job
from app.workers.embedding import run_embedding_job
from app.workers.ingestion import run_ingestion_job
from app.workers.vector_indexing import run_vector_indexing_job

router = APIRouter(prefix="/documents", tags=["Documents"])


def get_document_service(
    storage_provider: Annotated[StorageProvider, Depends(get_storage_provider)],
) -> DocumentService:
    """Dependency producing a DocumentService instance with the active storage provider."""
    return DocumentService(storage_provider=storage_provider)


def get_chunk_service(
    storage_provider: Annotated[StorageProvider, Depends(get_storage_provider)],
) -> DocumentChunkService:
    """Dependency producing a DocumentChunkService instance with active storage provider."""
    return DocumentChunkService(storage_provider=storage_provider)


def get_embedding_pipeline_service() -> DocumentEmbeddingPipelineService:
    """Dependency producing a DocumentEmbeddingPipelineService instance."""
    return DocumentEmbeddingPipelineService()


def get_vector_indexing_service(request: Request) -> DocumentVectorIndexingService:
    """Dependency producing a DocumentVectorIndexingService instance."""
    vs_service = getattr(request.app.state, "vector_store_service", None)
    return DocumentVectorIndexingService(vectorstore_service=vs_service)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload document",
    description="Upload and persist an enterprise document under the caller's tenant organization.",
    responses={
        status.HTTP_201_CREATED: {"description": "Document uploaded successfully"},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Bad request"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "Duplicate document"},
        getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413): {
            "model": ErrorResponse,
            "description": "File too large",
        },
        getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422): {
            "model": ErrorResponse,
            "description": "Validation failure",
        },
    },
)
async def upload_document(
    file: Annotated[UploadFile, File(description="File to upload (PDF, DOCX, TXT, CSV, XLSX)")],
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    background_tasks: BackgroundTasks,
    request: Request,
) -> DocumentResponse:
    """Upload a document file with streaming checksum, signature validation, and deduplication."""
    doc = await service.upload_document(session=session, tenant=tenant, file=file)
    if get_settings().AUTO_INGEST:
        factory = getattr(request.app.state, "db_session_factory", None)
        background_tasks.add_task(
            run_ingestion_job,
            organization_id=tenant.organization_id,
            document_id=doc.id,
            session_factory=factory,
            storage_provider=service.storage_provider,
        )
    return DocumentResponse.model_validate(doc)


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List documents",
    description="List active documents strictly scoped to caller's tenant organization.",
    responses={
        status.HTTP_200_OK: {"description": "Document list retrieved successfully"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
    },
)
async def list_documents(
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    skip: Annotated[int, Query(ge=0, description="Offset for pagination")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 50,
) -> DocumentListResponse:
    """List documents for the current tenant."""
    items, total = await service.list_documents(
        session=session,
        tenant=tenant,
        skip=skip,
        limit=limit,
    )
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(doc) for doc in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document details",
    description="Get metadata for document strictly scoped to caller's tenant organization.",
    responses={
        status.HTTP_200_OK: {"description": "Document metadata retrieved successfully"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def get_document(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentResponse:
    """Get metadata for a document by ID."""
    doc = await service.get_document(session=session, tenant=tenant, document_id=document_id)
    return DocumentResponse.model_validate(doc)


@router.get(
    "/{document_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download document file",
    description="Stream document content with safe headers and tenant authorization.",
    responses={
        status.HTTP_200_OK: {"description": "Document content stream"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def download_document(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> StreamingResponse:
    """Stream document content with sanitized download headers."""
    doc, stream = await service.download_document(
        session=session,
        tenant=tenant,
        document_id=document_id,
    )

    clean_name = sanitize_filename(doc.original_filename)
    # URL encode filename for RFC 5987 / safe headers
    encoded_name = urllib.parse.quote(clean_name)
    cd_header = f"attachment; filename=\"{clean_name}\"; filename*=UTF-8''{encoded_name}"

    headers = {
        "Content-Disposition": cd_header,
        "Content-Length": str(doc.file_size),
        "X-Content-Type-Options": "nosniff",
    }

    return StreamingResponse(
        stream,
        media_type=doc.mime_type,
        headers=headers,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete document",
    description="Safely soft-delete document metadata and purge storage object.",
    responses={
        status.HTTP_200_OK: {"description": "Document successfully deleted"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def delete_document(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_DELETE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    indexing_service: Annotated[
        DocumentVectorIndexingService, Depends(get_vector_indexing_service)
    ],
) -> dict[str, str]:
    """Delete a document by ID and purge its indexed vectors from Qdrant."""
    with contextlib.suppress(Exception):
        await indexing_service.delete_document_vectors(
            session=session,
            organization_id=tenant.organization_id,
            document_id=document_id,
        )

    await service.delete_document(
        session=session,
        tenant=tenant,
        document_id=document_id,
    )
    return {
        "detail": "Document successfully deleted.",
        "document_id": str(document_id),
    }


@router.post(
    "/{document_id}/ingest",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger document ingestion",
    description="Enqueue or synchronously run document parsing and normalization pipeline.",
    responses={
        status.HTTP_200_OK: {"description": "Document ingestion initiated or completed"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def ingest_document(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DocumentService, Depends(get_document_service)],
    background_tasks: BackgroundTasks,
    request: Request,
    sync: Annotated[bool, Query(description="Run ingestion synchronously in request")] = False,
) -> DocumentResponse:
    """Trigger ingestion for an existing document."""
    doc = await service.get_document(session=session, tenant=tenant, document_id=document_id)
    if sync:
        ingestion_service = IngestionService(db_session=session, storage=service.storage_provider)
        with contextlib.suppress(Exception):
            await ingestion_service.ingest_document(
                organization_id=tenant.organization_id,
                document_id=document_id,
            )
        doc = await service.get_document(session=session, tenant=tenant, document_id=document_id)
        return DocumentResponse.model_validate(doc)
    else:
        factory = getattr(request.app.state, "db_session_factory", None)
        background_tasks.add_task(
            run_ingestion_job,
            organization_id=tenant.organization_id,
            document_id=document_id,
            session_factory=factory,
            storage_provider=service.storage_provider,
        )
        return DocumentResponse.model_validate(doc)


@router.get(
    "/{document_id}/parsed",
    response_model=ParsedDocument,
    status_code=status.HTTP_200_OK,
    summary="Get canonical parsed document",
    description="Retrieve structured canonical parsed document ready for chunking.",
    responses={
        status.HTTP_200_OK: {"description": "Parsed document retrieved successfully"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Parsed document not found",
        },
    },
)
async def get_parsed_document(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> ParsedDocument:
    """Retrieve canonical parsed document representation."""
    await service.get_document(session=session, tenant=tenant, document_id=document_id)
    ingestion_service = IngestionService(db_session=session, storage=service.storage_provider)
    parsed = await ingestion_service.get_parsed_document(
        organization_id=tenant.organization_id,
        document_id=document_id,
    )
    if not parsed:
        raise NotFoundAppException(
            message=(
                f"Parsed representation for document {document_id} not found or not yet processed."
            ),
            code="PARSED_DOCUMENT_NOT_FOUND",
        )
    return parsed


@router.post(
    "/{document_id}/chunks",
    response_model=ChunkQualitySummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger document chunking",
    description=(
        "Analyze document structure, generate semantic parent/child chunks, "
        "and persist idempotently."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Chunking completed or enqueued successfully"},
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid document status or limits exceeded",
        },
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def chunk_document(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    chunk_service: Annotated[DocumentChunkService, Depends(get_chunk_service)],
    background_tasks: BackgroundTasks,
    request: Request,
    sync: Annotated[bool, Query(description="Run chunking synchronously in request")] = True,
) -> ChunkQualitySummaryResponse:
    """Trigger semantic chunking for a parsed document."""
    if sync:
        summary = await chunk_service.process_document_chunking(
            session=session,
            organization_id=tenant.organization_id,
            document_id=document_id,
        )
        return ChunkQualitySummaryResponse.model_validate(summary)
    else:
        factory = getattr(request.app.state, "db_session_factory", None)
        background_tasks.add_task(
            run_chunking_job,
            organization_id=tenant.organization_id,
            document_id=document_id,
            session_factory=factory,
            storage_provider=chunk_service.storage,
        )
        summary = await chunk_service.get_chunk_summary(
            session=session,
            organization_id=tenant.organization_id,
            document_id=document_id,
        )
        return ChunkQualitySummaryResponse.model_validate(summary)


@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunkListResponse,
    status_code=status.HTTP_200_OK,
    summary="List document chunks",
    description=(
        "Retrieve paginated list of semantic chunks scoped to tenant with optional parent filter."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Chunks retrieved successfully"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def list_document_chunks(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    chunk_service: Annotated[DocumentChunkService, Depends(get_chunk_service)],
    parent_only: Annotated[bool, Query(description="Filter to parent chunks only")] = False,
    skip: Annotated[int, Query(ge=0, description="Offset for pagination")] = 0,
    limit: Annotated[int, Query(ge=1, le=500, description="Page size limit")] = 100,
) -> DocumentChunkListResponse:
    """List chunks belonging to a document."""
    chunks, total = await chunk_service.list_chunks(
        session=session,
        organization_id=tenant.organization_id,
        document_id=document_id,
        parent_only=parent_only,
        skip=skip,
        limit=limit,
    )
    items = [DocumentChunkResponse.model_validate(c) for c in chunks]
    return DocumentChunkListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{document_id}/chunks/summary",
    response_model=ChunkQualitySummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get chunk quality summary",
    description=(
        "Retrieve quality metrics, token distributions, and coverage stats for document chunks."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Quality summary retrieved successfully"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def get_chunk_summary(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    chunk_service: Annotated[DocumentChunkService, Depends(get_chunk_service)],
) -> ChunkQualitySummaryResponse:
    """Retrieve quality metrics and distribution statistics for a document's chunks."""
    summary = await chunk_service.get_chunk_summary(
        session=session,
        organization_id=tenant.organization_id,
        document_id=document_id,
    )
    return ChunkQualitySummaryResponse.model_validate(summary)


@router.post(
    "/{document_id}/embeddings",
    response_model=DocumentEmbeddingSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate document embeddings",
    description=(
        "Transform document chunks into dense vector embeddings and persist metadata idempotently."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Embeddings generated or enqueued successfully"},
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid document status or limits exceeded",
        },
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def generate_document_embeddings(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    pipeline_service: Annotated[
        DocumentEmbeddingPipelineService, Depends(get_embedding_pipeline_service)
    ],
    background_tasks: BackgroundTasks,
    request: Request,
    payload: DocumentEmbeddingTriggerRequest | None = None,
    sync: Annotated[bool, Query(description="Run embedding synchronously in request")] = True,
    force: Annotated[bool, Query(description="Force re-embedding of existing chunks")] = False,
) -> DocumentEmbeddingSummaryResponse:
    """Trigger embedding generation for all chunks of a document."""
    is_sync = sync if payload is None else (payload.sync or sync)
    is_force = force if payload is None else (payload.force or force)

    if is_sync:
        return await pipeline_service.process_document_embeddings(
            session=session,
            organization_id=tenant.organization_id,
            document_id=document_id,
            force=is_force,
        )
    else:
        factory = getattr(request.app.state, "db_session_factory", None)
        background_tasks.add_task(
            run_embedding_job,
            organization_id=tenant.organization_id,
            document_id=document_id,
            force=is_force,
            session_factory=factory,
        )
        # Return summary of current state
        total = await pipeline_service.embedding_repo.count_by_document(
            session=session,
            organization_id=tenant.organization_id,
            document_id=document_id,
        )
        completed = await pipeline_service.embedding_repo.count_by_document(
            session=session,
            organization_id=tenant.organization_id,
            document_id=document_id,
            status="completed",
        )
        norm_mode = "l2" if pipeline_service.embedding_service.config.normalize else "none"
        return DocumentEmbeddingSummaryResponse(
            document_id=document_id,
            organization_id=tenant.organization_id,
            provider=pipeline_service.embedding_service.provider.provider_name,
            model=pipeline_service.embedding_service.config.model,
            version=pipeline_service.embedding_service.config.version,
            dimensions=pipeline_service.embedding_service.config.dimensions,
            normalization=norm_mode,
            total_embeddings=total,
            completed_count=completed,
            failed_count=total - completed,
            total_tokens=0,
            latency_ms=0.0,
            cache_hits=0,
            cache_misses=0,
            estimated_cost=None,
        )


@router.get(
    "/{document_id}/embeddings",
    response_model=DocumentChunkEmbeddingListResponse,
    status_code=status.HTTP_200_OK,
    summary="List document chunk embeddings",
    description="Retrieve paginated list of embedding metadata records for document chunks.",
    responses={
        status.HTTP_200_OK: {"description": "Embeddings retrieved successfully"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def list_document_embeddings(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    pipeline_service: Annotated[
        DocumentEmbeddingPipelineService, Depends(get_embedding_pipeline_service)
    ],
    skip: Annotated[int, Query(ge=0, description="Offset for pagination")] = 0,
    limit: Annotated[int, Query(ge=1, le=1000, description="Page size limit")] = 100,
) -> DocumentChunkEmbeddingListResponse:
    doc = await pipeline_service.document_repo.get_by_id(
        session=session,
        id=document_id,
        organization_id=tenant.organization_id,
    )
    if not doc:
        raise NotFoundAppException(
            message=f"Document {document_id} not found",
            code="DOCUMENT_NOT_FOUND",
        )

    records = await pipeline_service.embedding_repo.list_by_document(
        session=session,
        organization_id=tenant.organization_id,
        document_id=document_id,
        skip=skip,
        limit=limit,
    )

    total = await pipeline_service.embedding_repo.count_by_document(
        session=session,
        organization_id=tenant.organization_id,
        document_id=document_id,
    )
    items = [DocumentChunkEmbeddingResponse.model_validate(r) for r in records]
    return DocumentChunkEmbeddingListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/{document_id}/index",
    response_model=DocumentIndexingResponse,
    status_code=status.HTTP_200_OK,
    summary="Index document vectors in Qdrant",
    description=(
        "Transform document chunk embeddings into vector points and batch upsert into Qdrant."
    ),
    responses={
        status.HTTP_200_OK: {"description": "Document vectors indexed or enqueued successfully"},
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid document status or missing embeddings",
        },
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def index_document_vectors(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    indexing_service: Annotated[
        DocumentVectorIndexingService, Depends(get_vector_indexing_service)
    ],
    background_tasks: BackgroundTasks,
    request: Request,
    sync: Annotated[bool, Query(description="Run vector indexing synchronously in request")] = True,
    force: Annotated[bool, Query(description="Force re-indexing of vectors in Qdrant")] = False,
) -> DocumentIndexingResponse:
    """Trigger Qdrant vector indexing for a document."""
    if sync:
        return await indexing_service.index_document(
            session=session,
            organization_id=tenant.organization_id,
            document_id=document_id,
            force=force,
        )
    else:
        factory = getattr(request.app.state, "db_session_factory", None)
        background_tasks.add_task(
            run_vector_indexing_job,
            organization_id=tenant.organization_id,
            document_id=document_id,
            force=force,
            session_factory=factory,
        )
        status_info = await indexing_service.get_document_index_status(
            session=session,
            organization_id=tenant.organization_id,
            document_id=document_id,
        )
        return DocumentIndexingResponse(
            document_id=document_id,
            organization_id=tenant.organization_id,
            collection_name=status_info.collection_name,
            total_points=status_info.total_chunks,
            indexed_points=status_info.indexed_chunks,
            failed_points=0,
            latency_ms=0.0,
            status="pending",
        )


@router.get(
    "/{document_id}/index-status",
    response_model=DocumentIndexingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document vector indexing status",
    description="Retrieve Qdrant indexing progress and chunk coverage for a document.",
    responses={
        status.HTTP_200_OK: {"description": "Indexing status retrieved successfully"},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Forbidden"},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def get_document_index_status(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    indexing_service: Annotated[
        DocumentVectorIndexingService, Depends(get_vector_indexing_service)
    ],
) -> DocumentIndexingStatusResponse:
    """Retrieve vector indexing status for a document."""
    return await indexing_service.get_document_index_status(
        session=session,
        organization_id=tenant.organization_id,
        document_id=document_id,
    )

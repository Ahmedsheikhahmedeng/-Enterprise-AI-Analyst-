"""FastAPI router demonstrating tenant-isolated operations and cross-tenant access enforcement."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundAppException
from app.core.logging import get_logger
from app.db.postgres import get_db_session
from app.rbac.catalog import (
    PERM_DOCUMENTS_DELETE,
    PERM_DOCUMENTS_READ,
    PERM_DOCUMENTS_WRITE,
)
from app.repositories.document import DocumentRepository
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_current_tenant, require_tenant_permission
from app.tenancy.schemas import (
    CountResponse,
    CreateDocumentRequest,
    DocumentChunkResponse,
    DocumentResponse,
    TenantContextResponse,
    UpdateDocumentRequest,
)

logger = get_logger("tenancy.router")
tenant_router = APIRouter(prefix="/tenant", tags=["tenancy"])
_doc_repo = DocumentRepository()


@tenant_router.get(
    "/context",
    response_model=TenantContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspect caller's verified TenantContext",
)
async def get_tenant_context(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
) -> TenantContextResponse:
    """Return the request-scoped immutable TenantContext for the authenticated caller."""
    return TenantContextResponse(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        membership_id=tenant.membership_id,
        role_id=tenant.role_id,
        role_name=tenant.role_name,
        permissions=sorted(tenant.permissions),
    )


@tenant_router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a document in the active tenant",
)
async def create_document(
    payload: CreateDocumentRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentResponse:
    """Create a tenant-owned document.

    Guarantees that the new document is bound to the trusted TenantContext organization_id,
    even if the client payload maliciously specifies another organization_id.
    """
    doc = await _doc_repo.create(
        session=session,
        organization_id=tenant.organization_id,
        name=payload.name,
        original_filename=payload.original_filename,
        mime_type=payload.mime_type,
        file_size=payload.file_size,
        storage_key=payload.storage_key,
        status="uploaded",
        created_by=tenant.user_id,
    )
    await session.commit()
    return DocumentResponse.model_validate(doc)


@tenant_router.get(
    "/documents",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List tenant documents with scoped pagination",
)
async def list_documents(
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[DocumentResponse]:
    """List documents belonging strictly to the active tenant organization."""
    docs = await _doc_repo.list(
        session=session,
        organization_id=tenant.organization_id,
        skip=skip,
        limit=limit,
    )
    return [DocumentResponse.model_validate(doc) for doc in docs]


@tenant_router.get(
    "/documents/count",
    response_model=CountResponse,
    status_code=status.HTTP_200_OK,
    summary="Count tenant documents",
)
async def count_documents(
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CountResponse:
    """Return the total document count strictly within the caller's tenant organization."""
    total = await _doc_repo.count(session=session, organization_id=tenant.organization_id)
    return CountResponse(count=total, organization_id=tenant.organization_id)


@tenant_router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch document by ID with IDOR protection",
)
async def get_document(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentResponse:
    """Fetch a document by ID strictly scoped to the tenant organization.

    Employs safe 404 response to prevent IDOR resource enumeration across tenants.
    """
    doc = await _doc_repo.get_by_id(
        session=session,
        id=document_id,
        organization_id=tenant.organization_id,
    )
    if doc is None:
        logger.warning(
            "Document not found in tenant organization context (possible cross-tenant IDOR)",
            audit_event="cross_tenant_access_denied",
            user_id=str(tenant.user_id),
            organization_id=str(tenant.organization_id),
            resource_type="document",
            resource_id=str(document_id),
        )
        raise NotFoundAppException(message="Resource not found", code="NOT_FOUND")

    return DocumentResponse.model_validate(doc)


@tenant_router.put(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update document with tenant boundary enforcement",
)
async def update_document(
    document_id: uuid.UUID,
    payload: UpdateDocumentRequest,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_WRITE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentResponse:
    """Update a tenant document asserting both ID and organization_id."""
    update_data = payload.model_dump(exclude_unset=True)
    update_data.pop("organization_id", None)

    updated_doc = await _doc_repo.update(
        session=session,
        id=document_id,
        organization_id=tenant.organization_id,
        **update_data,
    )
    if updated_doc is None:
        logger.warning(
            "Cross-tenant document update rejected: resource does not exist in tenant",
            audit_event="cross_tenant_access_denied",
            user_id=str(tenant.user_id),
            organization_id=str(tenant.organization_id),
            resource_type="document",
            resource_id=str(document_id),
        )
        raise NotFoundAppException(message="Resource not found", code="NOT_FOUND")

    await session.commit()
    return DocumentResponse.model_validate(updated_doc)


@tenant_router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete document with tenant boundary enforcement",
)
async def delete_document(
    document_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_DELETE))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Delete a document asserting both ID and organization_id."""
    deleted = await _doc_repo.delete(
        session=session,
        id=document_id,
        organization_id=tenant.organization_id,
    )
    if not deleted:
        logger.warning(
            "Cross-tenant document deletion rejected: resource does not exist in tenant",
            audit_event="cross_tenant_access_denied",
            user_id=str(tenant.user_id),
            organization_id=str(tenant.organization_id),
            resource_type="document",
            resource_id=str(document_id),
        )
        raise NotFoundAppException(message="Resource not found", code="NOT_FOUND")

    await session.commit()
    return {"message": "Document deleted successfully."}


@tenant_router.get(
    "/documents/{document_id}/chunks/{chunk_id}",
    response_model=DocumentChunkResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch nested document chunk with parent and tenant validation",
)
async def get_document_chunk(
    document_id: uuid.UUID,
    chunk_id: uuid.UUID,
    tenant: Annotated[TenantContext, Depends(require_tenant_permission(PERM_DOCUMENTS_READ))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentChunkResponse:
    """Fetch nested DocumentChunk asserting chunk_id, document_id, and organization_id."""
    chunk = await _doc_repo.get_chunk(
        session=session,
        document_id=document_id,
        chunk_id=chunk_id,
        organization_id=tenant.organization_id,
    )
    if chunk is None:
        logger.warning(
            "Nested chunk traversal rejected: parent mismatch or cross-tenant lookup",
            audit_event="cross_tenant_access_denied",
            user_id=str(tenant.user_id),
            organization_id=str(tenant.organization_id),
            resource_type="document_chunk",
            document_id=str(document_id),
            chunk_id=str(chunk_id),
        )
        raise NotFoundAppException(message="Resource not found", code="NOT_FOUND")

    return DocumentChunkResponse.model_validate(chunk)

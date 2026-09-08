"""REST API router exposing Enterprise Agent Memory endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.postgres import get_db_session
from app.memory.exceptions import (
    MemoryAccessDeniedError,
    MemoryConflictError,
    MemoryNotFoundError,
    MemoryPrivacyViolationError,
    MemoryValidationError,
)
from app.memory.schemas import (
    MemoryItemCreateRequest,
    MemoryItemResponse,
    MemoryItemUpdateRequest,
    MemorySearchRequest,
    MemorySearchResponse,
    MemorySummaryResponse,
    MemoryType,
)
from app.memory.service import MemoryService
from app.models.user import User
from app.rbac.catalog import (
    PERM_MEMORY_CREATE,
    PERM_MEMORY_DELETE,
    PERM_MEMORY_READ,
    PERM_MEMORY_UPDATE,
)
from app.rbac.dependencies import require_permission
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_tenant_context

router = APIRouter(prefix="/memory", tags=["Agent Memory"])


@router.post(
    "",
    response_model=MemoryItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or record a memory item",
)
async def create_memory(
    request: MemoryItemCreateRequest,
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    _perm: Annotated[User, Depends(require_permission(PERM_MEMORY_CREATE))],
) -> MemoryItemResponse:
    """Store an explicit user-declared or derived memory item."""
    service = MemoryService()
    try:
        item = await service.create_memory(
            db_session=db_session,
            organization_id=tenant_context.organization_id,
            request=request,
            user_id=current_user.id,
            user_permissions={PERM_MEMORY_CREATE},
        )
        return MemoryItemResponse.model_validate(item)
    except MemoryPrivacyViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
    except MemoryConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc
    except MemoryValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc


@router.get(
    "",
    response_model=list[MemoryItemResponse],
    summary="List paginated memory items for tenant",
)
async def list_memories(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    _perm: Annotated[User, Depends(require_permission(PERM_MEMORY_READ))],
    memory_type: MemoryType | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MemoryItemResponse]:
    """Retrieve paginated active memories within tenant boundary."""
    service = MemoryService()
    types = [memory_type] if memory_type else None
    items, _ = await service.list_memories(
        db_session=db_session,
        organization_id=tenant_context.organization_id,
        memory_types=types,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        user_permissions={PERM_MEMORY_READ},
    )
    return [MemoryItemResponse.model_validate(it) for it in items]


@router.get(
    "/summary",
    response_model=MemorySummaryResponse,
    summary="Get memory counts by tier and status",
)
async def get_memory_summary(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    _perm: Annotated[User, Depends(require_permission(PERM_MEMORY_READ))],
) -> MemorySummaryResponse:
    """Fetch breakdown of stored memories by type, status, and privacy tier."""
    service = MemoryService()
    return await service.get_summary(
        db_session=db_session,
        organization_id=tenant_context.organization_id,
        user_permissions={PERM_MEMORY_READ},
    )


@router.post(
    "/search",
    response_model=MemorySearchResponse,
    summary="Search memories semantically",
)
async def search_memories(
    request: MemorySearchRequest,
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    _perm: Annotated[User, Depends(require_permission(PERM_MEMORY_READ))],
) -> MemorySearchResponse:
    """Perform hybrid semantic vector and metadata search over tenant memories."""
    service = MemoryService()
    results = await service.search_memories(
        db_session=db_session,
        organization_id=tenant_context.organization_id,
        request=request,
        user_id=current_user.id,
        user_permissions={PERM_MEMORY_READ},
    )
    return MemorySearchResponse(
        query=request.query,
        total_found=len(results),
        results=results,
    )


@router.get(
    "/{memory_id}",
    response_model=MemoryItemResponse,
    summary="Get memory item by ID",
)
async def get_memory(
    memory_id: uuid.UUID,
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    _perm: Annotated[User, Depends(require_permission(PERM_MEMORY_READ))],
) -> MemoryItemResponse:
    """Fetch single memory item with access authorization."""
    service = MemoryService()
    try:
        item = await service.get_memory(
            db_session=db_session,
            memory_id=memory_id,
            organization_id=tenant_context.organization_id,
            user_id=current_user.id,
            user_permissions={PERM_MEMORY_READ},
        )
        return MemoryItemResponse.model_validate(item)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except MemoryAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message) from exc


@router.delete(
    "/{memory_id}",
    response_model=MemoryItemResponse,
    summary="Soft-delete memory item",
)
async def delete_memory(
    memory_id: uuid.UUID,
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    _perm: Annotated[User, Depends(require_permission(PERM_MEMORY_DELETE))],
) -> MemoryItemResponse:
    """Mark memory item as deleted (tombstone) and evict from vector index."""
    service = MemoryService()
    try:
        item = await service.delete_memory(
            db_session=db_session,
            memory_id=memory_id,
            organization_id=tenant_context.organization_id,
            user_id=current_user.id,
            user_permissions={PERM_MEMORY_DELETE},
        )
        return MemoryItemResponse.model_validate(item)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except MemoryAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message) from exc


@router.patch(
    "/{memory_id}",
    response_model=MemoryItemResponse,
    summary="Update memory item",
)
async def update_memory(
    memory_id: uuid.UUID,
    request: MemoryItemUpdateRequest,
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    current_user: Annotated[User, Depends(get_current_user)],
    _perm: Annotated[User, Depends(require_permission(PERM_MEMORY_UPDATE))],
) -> MemoryItemResponse:
    """Update memory item, creating a new historical version."""
    service = MemoryService()
    try:
        item = await service.update_memory(
            db_session=db_session,
            memory_id=memory_id,
            organization_id=tenant_context.organization_id,
            request=request,
            user_id=current_user.id,
            user_permissions={PERM_MEMORY_UPDATE},
        )
        return MemoryItemResponse.model_validate(item)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except MemoryAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.message) from exc
    except MemoryPrivacyViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc

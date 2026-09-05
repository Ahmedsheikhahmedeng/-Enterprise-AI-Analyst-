"""Pydantic schemas for tenant-isolated operations and demonstration endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenantContextResponse(BaseModel):
    """Schema returning the active resolved TenantContext."""

    organization_id: uuid.UUID
    user_id: uuid.UUID
    membership_id: uuid.UUID
    role_id: uuid.UUID
    role_name: str
    permissions: list[str] = Field(default_factory=list)


class CreateDocumentRequest(BaseModel):
    """Schema for creating a tenant document.

    Note: Any client-provided organization_id will be ignored by the backend,
    which always derives tenant ownership from the trusted TenantContext.
    """

    name: str
    original_filename: str
    mime_type: str = "application/pdf"
    file_size: int
    storage_key: str
    # Optional field that an attacker might try to send to hijack ownership
    organization_id: uuid.UUID | None = None


class UpdateDocumentRequest(BaseModel):
    """Schema for updating a tenant document."""

    name: str | None = None
    mime_type: str | None = None
    # Optional field that an attacker might try to send
    organization_id: uuid.UUID | None = None


class DocumentResponse(BaseModel):
    """Schema representing a tenant-scoped document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    original_filename: str
    mime_type: str
    file_size: int
    storage_key: str
    status: str
    created_at: datetime


class DocumentChunkResponse(BaseModel):
    """Schema representing a nested document chunk."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    organization_id: uuid.UUID
    chunk_index: int
    content: str
    created_at: datetime


class CountResponse(BaseModel):
    """Schema for tenant resource count queries."""

    count: int
    organization_id: uuid.UUID

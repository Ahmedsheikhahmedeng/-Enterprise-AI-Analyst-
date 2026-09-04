"""Pydantic schemas for RBAC and authorization endpoints."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class RoleResponse(BaseModel):
    """Schema representing an RBAC role definition."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    organization_id: uuid.UUID | None = None
    permissions: list[str] = Field(default_factory=list)


class AssignRoleRequest(BaseModel):
    """Schema for assigning an RBAC role to an organization member."""

    user_id: uuid.UUID
    role_id: uuid.UUID
    organization_id: uuid.UUID | None = None


class RemoveRoleRequest(BaseModel):
    """Schema for removing an organization member's role/membership."""

    user_id: uuid.UUID
    organization_id: uuid.UUID | None = None


class UserEffectivePermissionsResponse(BaseModel):
    """Schema returning the effective permissions of a user in an organization."""

    user_id: uuid.UUID
    organization_id: uuid.UUID
    role_id: uuid.UUID | None = None
    role_name: str | None = None
    permissions: list[str] = Field(default_factory=list)


class RBACActionResponse(BaseModel):
    """Standard message response for RBAC operational actions."""

    message: str
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role_id: uuid.UUID | None = None

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload for user registration."""

    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters.")
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    """Payload for user authentication."""

    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """Standardized bearer token response returned upon successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifespan in seconds")


class CurrentUserResponse(BaseModel):
    """Public profile representation of the currently authenticated user."""

    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RefreshRequest(BaseModel):
    """Payload for exchanging an existing refresh token for a new token pair."""

    refresh_token: str = Field(min_length=1, description="Opaque refresh token")


class LogoutRequest(BaseModel):
    """Optional payload for revoking a specific refresh token during logout."""

    refresh_token: str | None = Field(default=None, description="Optional refresh token to revoke")


class ChangePasswordRequest(BaseModel):
    """Payload for an authenticated user updating their password."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(
        min_length=8, description="New password must be at least 8 characters."
    )


class ForgotPasswordRequest(BaseModel):
    """Payload for initiating a password reset workflow."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Payload for consuming a password reset token and defining a new password."""

    token: str = Field(min_length=1)
    new_password: str = Field(
        min_length=8, description="New password must be at least 8 characters."
    )


class VerifyEmailRequest(BaseModel):
    """Payload for confirming email ownership using a single-use verification token."""

    token: str = Field(min_length=1)


class ResendVerificationRequest(BaseModel):
    """Payload for re-triggering an email verification message."""

    email: EmailStr


class MessageResponse(BaseModel):
    """Generic status response envelope for informational operations."""

    message: str
    details: dict[str, Any] | None = None

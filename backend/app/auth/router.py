from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import (
    ChangePasswordRequest,
    CurrentUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.auth.service import AuthService
from app.db.postgres import get_db_session
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])
auth_service = AuthService()

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def _extract_client_metadata(request: Request) -> tuple[str | None, str | None]:
    """Extract client IP and User-Agent from HTTP request headers."""
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    return user_agent, client_ip


@router.post(
    "/register",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    payload: RegisterRequest,
    session: SessionDep,
) -> User:
    """Register a new user with secure password hashing."""
    user = await auth_service.register(session, payload)
    await session.commit()
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue JWT + refresh token",
)
async def login(
    payload: LoginRequest,
    request: Request,
    session: SessionDep,
) -> TokenResponse:
    """Authenticate email and password, creating a tracked refresh session."""
    user_agent, ip_address = _extract_client_metadata(request)
    tokens = await auth_service.login(
        session=session,
        payload=payload,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    await session.commit()
    return tokens


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve profile of currently authenticated user",
)
async def get_me(
    current_user: CurrentUserDep,
) -> User:
    """Return the profile data of the caller based on their validated JWT access token."""
    return current_user


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token session and issue a new token pair",
)
async def refresh_tokens(
    payload: RefreshRequest,
    request: Request,
    session: SessionDep,
) -> TokenResponse:
    """Rotate an active refresh token with single-use reuse detection."""
    user_agent, ip_address = _extract_client_metadata(request)
    tokens = await auth_service.refresh(
        session=session,
        raw_refresh_token=payload.refresh_token,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    await session.commit()
    return tokens


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke refresh token session",
)
async def logout(
    session: SessionDep,
    payload: LogoutRequest | None = None,
) -> MessageResponse:
    """Revoke the current refresh token session."""
    raw_token = payload.refresh_token if payload else None
    await auth_service.logout(session, raw_token)
    await session.commit()
    return MessageResponse(message="Successfully logged out.")


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke all active sessions for authenticated user",
)
async def logout_all(
    current_user: CurrentUserDep,
    session: SessionDep,
) -> MessageResponse:
    """Invalidate all refresh token sessions belonging to the current user."""
    count = await auth_service.logout_all(session, current_user)
    await session.commit()
    return MessageResponse(
        message="Successfully revoked all active sessions.",
        details={"revoked_sessions_count": count},
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change password for authenticated user and invalidate sessions",
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> MessageResponse:
    """Verify current password and set new password, revoking existing refresh sessions."""
    await auth_service.change_password(session, current_user, payload)
    await session.commit()
    return MessageResponse(
        message="Password successfully changed. Please log in with your new password."
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Initiate single-use password reset workflow",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: SessionDep,
) -> MessageResponse:
    """Initiate password reset. Does not reveal account existence."""
    dev_token = await auth_service.forgot_password(session, payload.email)
    await session.commit()

    details = {"dev_reset_token": dev_token} if dev_token else None
    return MessageResponse(
        message=(
            "If the provided email corresponds to an active account, "
            "password reset instructions have been initiated."
        ),
        details=details,
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete password reset using single-use token",
)
async def reset_password(
    payload: ResetPasswordRequest,
    session: SessionDep,
) -> MessageResponse:
    """Consume a valid password reset token and update password."""
    await auth_service.reset_password(session, payload)
    await session.commit()
    return MessageResponse(message="Password has been reset successfully. You may now log in.")


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm email address using single-use verification token",
)
async def verify_email(
    payload: VerifyEmailRequest,
    session: SessionDep,
) -> MessageResponse:
    """Verify user's email address."""
    await auth_service.verify_email(session, payload.token)
    await session.commit()
    return MessageResponse(message="Email address has been successfully verified.")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Request a new email verification token",
)
async def resend_verification(
    payload: ResendVerificationRequest,
    session: SessionDep,
) -> MessageResponse:
    """Re-issue email verification token without leaking account status."""
    dev_token = await auth_service.resend_verification(session, payload.email)
    await session.commit()

    details = {"dev_verification_token": dev_token} if dev_token else None
    return MessageResponse(
        message=(
            "If the provided email is registered and unverified, "
            "a verification link has been initiated."
        ),
        details=details,
    )

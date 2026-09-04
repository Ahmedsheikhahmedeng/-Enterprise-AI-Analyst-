from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password, validate_password_policy, verify_password
from app.auth.repository import AuthRepository
from app.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.auth.tokens import generate_secure_token, hash_token
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedAppException, ValidationAppException
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger("auth")


class AuthService:
    """Orchestrates identity and authentication business logic with strict security logging."""

    def __init__(self, repository: AuthRepository | None = None) -> None:
        self.repo = repository or AuthRepository()

    async def register(self, session: AsyncSession, payload: RegisterRequest) -> User:
        """Register a new user account with Argon2id password hashing.

        Guards against user enumeration by returning a generic validation failure
        on duplicate email.
        """
        validate_password_policy(payload.password)
        normalized_email = payload.email.strip().lower()

        existing_user = await self.repo.get_user_by_email(session, normalized_email)
        if existing_user is not None:
            # Generic response prevents account existence enumeration
            raise ValidationAppException(
                message=(
                    "Unable to complete registration with the provided details. "
                    "If you already have an account, please log in."
                ),
                code="REGISTRATION_FAILED",
            )

        password_hash = hash_password(payload.password)
        user = await self.repo.create_user(
            session=session,
            email=normalized_email,
            password_hash=password_hash,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
        logger.info(
            "User registered successfully",
            auth_event="user_registered",
            user_id=str(user.id),
        )
        return user

    async def login(
        self,
        session: AsyncSession,
        payload: LoginRequest,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResponse:
        """Authenticate user credentials and issue an access token + refresh token session."""
        settings = get_settings()
        normalized_email = payload.email.strip().lower()

        user = await self.repo.get_user_by_email(session, normalized_email)
        if user is None or not user.is_active:
            logger.warning(
                "Authentication failed: user not found or inactive",
                auth_event="login_failure",
            )
            raise UnauthorizedAppException(
                message="Invalid email or password.",
                code="INVALID_CREDENTIALS",
            )

        if not verify_password(payload.password, user.password_hash):
            logger.warning(
                "Authentication failed: incorrect password",
                auth_event="login_failure",
                user_id=str(user.id),
            )
            raise UnauthorizedAppException(
                message="Invalid email or password.",
                code="INVALID_CREDENTIALS",
            )

        access_token = create_access_token(user.id)
        raw_refresh_token = generate_secure_token()
        token_hash = hash_token(raw_refresh_token)
        refresh_expires = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        await self.repo.create_refresh_token(
            session=session,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=refresh_expires,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        logger.info(
            "User logged in successfully",
            auth_event="login_success",
            user_id=str(user.id),
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh(
        self,
        session: AsyncSession,
        raw_refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResponse:
        """Rotate a refresh token session with reuse detection and issue a new token pair."""
        settings = get_settings()
        token_hash = hash_token(raw_refresh_token)

        # Retrieve session with exclusive row lock to protect against race conditions
        token_record = await self.repo.get_refresh_token_by_hash_for_update(session, token_hash)
        if token_record is None:
            logger.warning(
                "Refresh failed: token hash not found",
                auth_event="refresh_failure",
            )
            raise UnauthorizedAppException(
                message="Invalid or expired refresh token.",
                code="INVALID_REFRESH_TOKEN",
            )

        # REUSE DETECTION: Presenting a previously revoked token indicates token compromise
        if token_record.revoked_at is not None:
            logger.error(
                "SECURITY ALERT: Revoked refresh token reuse detected! Invalidating token family.",
                auth_event="refresh_reuse_detected",
                user_id=str(token_record.user_id),
                family_id=str(token_record.family_id),
                token_session_id=str(token_record.id),
            )
            # Invalidate all active sessions in this token family
            await self.repo.revoke_token_family(session, token_record.family_id)
            await session.commit()
            raise UnauthorizedAppException(
                message="Suspicious session activity detected. Please log in again.",
                code="REFRESH_TOKEN_REUSED",
            )

        # Verify expiration
        now = datetime.now(UTC)
        if token_record.expires_at <= now:
            logger.warning(
                "Refresh failed: refresh token expired",
                auth_event="refresh_failure",
                user_id=str(token_record.user_id),
            )
            raise UnauthorizedAppException(
                message="Refresh token has expired. Please log in again.",
                code="REFRESH_TOKEN_EXPIRED",
            )

        user = await self.repo.get_user_by_id(session, token_record.user_id)
        if user is None or not user.is_active:
            logger.warning(
                "Refresh failed: user inactive or not found",
                auth_event="refresh_failure",
                user_id=str(token_record.user_id),
            )
            raise UnauthorizedAppException(
                message="User account is inactive or disabled.",
                code="INACTIVE_USER",
            )

        # Revoke the old token atomically
        await self.repo.revoke_refresh_token(session, token_record)

        # Issue new token pair (rotation preserving family_id)
        new_raw_refresh_token = generate_secure_token()
        new_token_hash = hash_token(new_raw_refresh_token)
        new_refresh_expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        await self.repo.create_refresh_token(
            session=session,
            user_id=user.id,
            family_id=token_record.family_id,
            token_hash=new_token_hash,
            expires_at=new_refresh_expires,
            rotated_from_id=token_record.id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        new_access_token = create_access_token(user.id)
        logger.info(
            "Refresh token rotated successfully",
            auth_event="refresh_success",
            user_id=str(user.id),
        )
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_raw_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, session: AsyncSession, raw_refresh_token: str | None) -> None:
        """Revoke the presented refresh token session."""
        if raw_refresh_token:
            token_hash = hash_token(raw_refresh_token)
            token_record = await self.repo.get_refresh_token_by_hash(session, token_hash)
            if token_record and token_record.revoked_at is None:
                await self.repo.revoke_refresh_token(session, token_record)
                logger.info(
                    "Refresh token revoked on logout",
                    auth_event="logout",
                    user_id=str(token_record.user_id),
                )
                return
        logger.info("Logout processed", auth_event="logout")

    async def logout_all(self, session: AsyncSession, current_user: User) -> int:
        """Revoke all active refresh sessions belonging to the authenticated user."""
        revoked_count = await self.repo.revoke_all_user_refresh_tokens(session, current_user.id)
        logger.info(
            "All user sessions revoked",
            auth_event="logout_all",
            user_id=str(current_user.id),
            count=revoked_count,
        )
        return revoked_count

    async def change_password(
        self, session: AsyncSession, current_user: User, payload: ChangePasswordRequest
    ) -> None:
        """Verify current password, update to new Argon2 hash, and revoke existing sessions."""
        if not verify_password(payload.current_password, current_user.password_hash):
            raise UnauthorizedAppException(
                message="Current password is incorrect.",
                code="INVALID_CREDENTIALS",
            )

        validate_password_policy(payload.new_password)
        if payload.new_password == payload.current_password:
            raise ValidationAppException(
                message="New password must be different from your current password.",
                code="SAME_PASSWORD",
            )

        new_hash = hash_password(payload.new_password)
        await self.repo.update_user_password(session, current_user, new_hash)
        # Immediately invalidate all sessions to force re-authentication with new credentials
        await self.repo.revoke_all_user_refresh_tokens(session, current_user.id)

        logger.info(
            "Password changed successfully; all sessions revoked",
            auth_event="password_changed",
            user_id=str(current_user.id),
        )

    async def forgot_password(self, session: AsyncSession, email: str) -> str | None:
        """Generate a single-use password reset token."""
        settings = get_settings()
        normalized_email = email.strip().lower()
        user = await self.repo.get_user_by_email(session, normalized_email)

        dev_token: str | None = None
        if user is not None and user.is_active:
            raw_token = generate_secure_token()
            token_hash = hash_token(raw_token)
            expires_at = datetime.now(UTC) + timedelta(
                minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
            )
            await self.repo.create_password_reset_token(
                session=session,
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            logger.info(
                "Password reset token issued",
                auth_event="password_reset_requested",
                user_id=str(user.id),
            )
            # Only expose token in development/testing environments for automated testing
            if settings.is_development or settings.is_testing:
                dev_token = raw_token

        return dev_token

    async def reset_password(self, session: AsyncSession, payload: ResetPasswordRequest) -> None:
        """Consume a password reset token and update the user's password."""
        token_hash = hash_token(payload.token)
        reset_token = await self.repo.get_valid_password_reset_token(session, token_hash)
        if reset_token is None:
            raise UnauthorizedAppException(
                message="Invalid or expired password reset token.",
                code="INVALID_RESET_TOKEN",
            )

        user = await self.repo.get_user_by_id(session, reset_token.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedAppException(
                message="User account is inactive or not found.",
                code="INACTIVE_USER",
            )

        validate_password_policy(payload.new_password)
        new_hash = hash_password(payload.new_password)
        await self.repo.update_user_password(session, user, new_hash)
        await self.repo.consume_password_reset_token(session, reset_token)
        # Invalidate existing refresh sessions
        await self.repo.revoke_all_user_refresh_tokens(session, user.id)

        logger.info(
            "Password reset completed",
            auth_event="password_reset_completed",
            user_id=str(user.id),
        )

    async def verify_email(self, session: AsyncSession, token: str) -> None:
        """Consume an email verification token and update user's verification status."""
        token_hash = hash_token(token)
        verification_token = await self.repo.get_valid_email_verification_token(session, token_hash)
        if verification_token is None:
            raise UnauthorizedAppException(
                message="Invalid or expired email verification token.",
                code="INVALID_VERIFICATION_TOKEN",
            )

        user = await self.repo.get_user_by_id(session, verification_token.user_id)
        if user is None:
            raise UnauthorizedAppException(
                message="User account not found.",
                code="NOT_FOUND",
            )

        await self.repo.mark_user_verified(session, user)
        await self.repo.consume_email_verification_token(session, verification_token)

        logger.info(
            "Email verified successfully",
            auth_event="email_verified",
            user_id=str(user.id),
        )

    async def resend_verification(self, session: AsyncSession, email: str) -> str | None:
        """Generate a new email verification token if the account exists and is unverified."""
        settings = get_settings()
        normalized_email = email.strip().lower()
        user = await self.repo.get_user_by_email(session, normalized_email)

        dev_token: str | None = None
        if user is not None and not user.is_verified:
            raw_token = generate_secure_token()
            token_hash = hash_token(raw_token)
            expires_at = datetime.now(UTC) + timedelta(
                hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
            )
            await self.repo.create_email_verification_token(
                session=session,
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            if settings.is_development or settings.is_testing:
                dev_token = raw_token

        return dev_token

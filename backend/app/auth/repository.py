import uuid
from datetime import UTC, datetime

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import EmailVerificationToken, PasswordResetToken, RefreshToken
from app.models.user import User


class AuthRepository:
    """Encapsulates all database queries and updates for users and authentication tokens."""

    async def get_user_by_email(self, session: AsyncSession, email: str) -> User | None:
        """Find a user record by case-insensitive email address."""
        stmt = select(User).where(User.email == email.strip().lower())
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, session: AsyncSession, user_id: uuid.UUID) -> User | None:
        """Retrieve a user by unique identifier."""
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        session: AsyncSession,
        email: str,
        password_hash: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """Persist a new user entity with a pre-hashed password."""
        user = User(
            email=email.strip().lower(),
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_verified=False,
        )
        session.add(user)
        await session.flush()
        return user

    async def update_user_password(
        self, session: AsyncSession, user: User, new_password_hash: str
    ) -> None:
        """Update the stored Argon2 password hash for an existing user."""
        user.password_hash = new_password_hash
        await session.flush()

    async def mark_user_verified(self, session: AsyncSession, user: User) -> None:
        """Mark user's email verification status as verified."""
        user.is_verified = True
        await session.flush()

    # --------------------------------------------------------------------------
    # Refresh Token Session Management
    # --------------------------------------------------------------------------
    async def create_refresh_token(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        family_id: uuid.UUID | None = None,
        rotated_from_id: uuid.UUID | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> RefreshToken:
        """Store a new hashed refresh token session."""
        refresh_token = RefreshToken(
            user_id=user_id,
            family_id=family_id or uuid.uuid4(),
            token_hash=token_hash,
            expires_at=expires_at,
            rotated_from_id=rotated_from_id,
            user_agent=user_agent[:500] if user_agent else None,
            ip_address=ip_address[:100] if ip_address else None,
        )
        session.add(refresh_token)
        await session.flush()
        return refresh_token

    async def revoke_token_family(self, session: AsyncSession, family_id: uuid.UUID) -> int:
        """Revoke all active refresh sessions belonging to the same token lineage family."""
        now = datetime.now(UTC)
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        result = await session.execute(stmt)
        await session.flush()
        return int(result.rowcount) if isinstance(result, CursorResult) else 0

    async def get_refresh_token_by_hash_for_update(
        self, session: AsyncSession, token_hash: str
    ) -> RefreshToken | None:
        """Retrieve a refresh token session using an exclusive row lock for race safety."""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_refresh_token_by_hash(
        self, session: AsyncSession, token_hash: str
    ) -> RefreshToken | None:
        """Retrieve a refresh token session without a row lock."""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_refresh_token(
        self, session: AsyncSession, refresh_token: RefreshToken
    ) -> None:
        """Revoke a single refresh token session."""
        refresh_token.revoked_at = datetime.now(UTC)
        await session.flush()

    async def revoke_all_user_refresh_tokens(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> int:
        """Revoke all active refresh sessions belonging to a specific user."""
        now = datetime.now(UTC)
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        result = await session.execute(stmt)
        await session.flush()
        return int(result.rowcount) if isinstance(result, CursorResult) else 0

    # --------------------------------------------------------------------------
    # Password Reset Tokens
    # --------------------------------------------------------------------------
    async def create_password_reset_token(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        """Persist a single-use hashed password reset token."""
        reset_token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.add(reset_token)
        await session.flush()
        return reset_token

    async def get_valid_password_reset_token(
        self, session: AsyncSession, token_hash: str
    ) -> PasswordResetToken | None:
        """Locate an active, unconsumed password reset token that has not expired."""
        now = datetime.now(UTC)
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def consume_password_reset_token(
        self, session: AsyncSession, reset_token: PasswordResetToken
    ) -> None:
        """Mark a password reset token as consumed."""
        reset_token.used_at = datetime.now(UTC)
        await session.flush()

    # --------------------------------------------------------------------------
    # Email Verification Tokens
    # --------------------------------------------------------------------------
    async def create_email_verification_token(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> EmailVerificationToken:
        """Persist a single-use hashed email verification token."""
        verification_token = EmailVerificationToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.add(verification_token)
        await session.flush()
        return verification_token

    async def get_valid_email_verification_token(
        self, session: AsyncSession, token_hash: str
    ) -> EmailVerificationToken | None:
        """Locate an active, unconsumed email verification token that has not expired."""
        now = datetime.now(UTC)
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.expires_at > now,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def consume_email_verification_token(
        self, session: AsyncSession, token: EmailVerificationToken
    ) -> None:
        """Mark an email verification token as consumed."""
        token.used_at = datetime.now(UTC)
        await session.flush()

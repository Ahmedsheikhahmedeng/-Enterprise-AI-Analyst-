import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import hash_token
from app.core.config import get_settings
from app.db.postgres import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from app.main import create_app
from app.models.auth import EmailVerificationToken, PasswordResetToken, RefreshToken
from app.models.user import User


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient wired to FastAPI app instance with PostgreSQL database state."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await dispose_database_engine(engine)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide real PostgreSQL session for DB state verification."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        yield session
    await dispose_database_engine(engine)


@pytest.mark.asyncio
async def test_registration_success_and_duplicate_enumeration_protection(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify user registration, Argon2id hashing, and duplicate email protection."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"user_{unique_suffix}@example.com"
    password = "SecurePassword123!"

    # 1. Successful registration
    response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Alice",
            "last_name": "Smith",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert data["first_name"] == "Alice"
    assert data["last_name"] == "Smith"
    assert "password" not in data
    assert "password_hash" not in data

    # 2. Verify database record: Plaintext password is NEVER stored
    stmt = select(User).where(User.email == email)
    user = (await db_session.execute(stmt)).scalar_one()
    assert user.password_hash != password
    assert user.password_hash.startswith("$argon2id$")

    # 3. Duplicate email registration rejected with generic message (no enumeration)
    dup_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "AnotherPassword456!",
        },
    )
    assert dup_resp.status_code == 422
    dup_data = dup_resp.json()
    assert dup_data["error"]["code"] == "REGISTRATION_FAILED"

    # 4. Weak password rejected
    weak_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"weak_{unique_suffix}@example.com",
            "password": "short",
        },
    )
    assert weak_resp.status_code == 422


@pytest.mark.asyncio
async def test_login_and_token_storage_security(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify login authentication, token responses, and hashed refresh token persistence."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"login_{unique_suffix}@example.com"
    password = "ValidPassword123!"

    # Register user
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert reg_resp.status_code == 201

    # 1. Successful login
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["expires_in"] == 900

    raw_refresh = token_data["refresh_token"]

    # 2. Database check: Raw refresh token MUST NOT be stored in DB
    hashed_token = hash_token(raw_refresh)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == hashed_token)
    token_record = (await db_session.execute(stmt)).scalar_one_or_none()
    assert token_record is not None
    assert token_record.token_hash != raw_refresh

    # Check raw token does not exist anywhere as plain string
    raw_stmt = select(RefreshToken).where(RefreshToken.token_hash == raw_refresh)
    assert (await db_session.execute(raw_stmt)).scalar_one_or_none() is None

    # 3. Wrong password failure (401 generic error)
    wrong_pwd_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword!"},
    )
    assert wrong_pwd_resp.status_code == 401
    assert wrong_pwd_resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    # 4. Unknown email failure (401 generic error, identical to wrong password)
    unknown_email_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": password},
    )
    assert unknown_email_resp.status_code == 401
    assert unknown_email_resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_current_user_me_endpoint(async_client: AsyncClient) -> None:
    """Verify /me endpoint authorization, malformed token handling, and data sanitization."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"me_{unique_suffix}@example.com"
    password = "MyPassword123!"

    # Register & login
    await async_client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_resp = await async_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    tokens = login_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # 1. Valid access token
    me_resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 200
    user_data = me_resp.json()
    assert user_data["email"] == email
    assert "password_hash" not in user_data

    # 2. Missing authorization header
    missing_resp = await async_client.get("/api/v1/auth/me")
    assert missing_resp.status_code == 401

    # 3. Malformed token
    bad_resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert bad_resp.status_code == 401

    # 4. Refresh token used as Bearer token must fail (INVALID_TOKEN_TYPE)
    refresh_as_access = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert refresh_as_access.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_reuse_detection(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify refresh token rotation and security detection on token reuse."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"rot_{unique_suffix}@example.com"
    password = "ValidPassword123!"

    await async_client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_resp = await async_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    initial_refresh = login_resp.json()["refresh_token"]

    # 1. Rotate refresh token
    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()
    rotated_refresh = new_tokens["refresh_token"]
    assert rotated_refresh != initial_refresh

    # 2. Verify in DB: initial refresh token is revoked, rotated token references it
    initial_hash = hash_token(initial_refresh)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == initial_hash)
    old_record = (await db_session.execute(stmt)).scalar_one()
    assert old_record.revoked_at is not None

    rotated_hash = hash_token(rotated_refresh)
    stmt_new = select(RefreshToken).where(RefreshToken.token_hash == rotated_hash)
    new_record = (await db_session.execute(stmt_new)).scalar_one()
    assert new_record.revoked_at is None
    assert new_record.rotated_from_id == old_record.id

    # 3. REUSE DETECTION: Presenting initial (now revoked) refresh token again
    reuse_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert reuse_resp.status_code == 401
    assert reuse_resp.json()["error"]["code"] == "REFRESH_TOKEN_REUSED"

    # 4. Verify family revocation: new_record should now ALSO be revoked
    await db_session.commit()
    db_session.expire_all()
    refreshed_new_record = (await db_session.execute(stmt_new)).scalar_one()
    assert refreshed_new_record.revoked_at is not None

    # The rotated token can no longer be used
    failed_new_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": rotated_refresh},
    )
    assert failed_new_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_and_logout_all(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify logout revokes the current session and logout-all invalidates all user sessions."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"logout_{unique_suffix}@example.com"
    password = "ValidPassword123!"

    await async_client.post("/api/v1/auth/register", json={"email": email, "password": password})

    # Device 1 login
    login1 = (
        await async_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    ).json()
    # Device 2 login
    login2 = (
        await async_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    ).json()

    # Logout device 1
    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": login1["refresh_token"]},
    )
    assert logout_resp.status_code == 200

    # Device 1 refresh fails
    assert (
        await async_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": login1["refresh_token"]}
        )
    ).status_code == 401

    # Device 2 refresh still succeeds
    assert (
        await async_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": login2["refresh_token"]}
        )
    ).status_code == 200

    # Logout All using device 2's access token
    logout_all_resp = await async_client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {login2['access_token']}"},
    )
    assert logout_all_resp.status_code == 200

    # Now all refresh tokens for this user are revoked
    await db_session.commit()
    user_stmt = select(User).where(User.email == email)
    user = (await db_session.execute(user_stmt)).scalar_one()

    stmt = select(RefreshToken).where(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    )
    active_tokens = (await db_session.execute(stmt)).scalars().all()
    assert len(active_tokens) == 0


@pytest.mark.asyncio
async def test_change_password_workflow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify authenticated password change, old password rejection, and session invalidation."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"pwd_{unique_suffix}@example.com"
    old_pwd = "OldPassword123!"
    new_pwd = "NewSecurePassword456!"

    await async_client.post("/api/v1/auth/register", json={"email": email, "password": old_pwd})
    login_resp = await async_client.post(
        "/api/v1/auth/login", json={"email": email, "password": old_pwd}
    )
    tokens = login_resp.json()

    # 1. Invalid current password fails
    fail_change = await async_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"current_password": "WrongPassword!", "new_password": new_pwd},
    )
    assert fail_change.status_code == 401

    # 2. Same password rejected
    same_pwd_change = await async_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"current_password": old_pwd, "new_password": old_pwd},
    )
    assert same_pwd_change.status_code == 422

    # 3. Successful change
    success_change = await async_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"current_password": old_pwd, "new_password": new_pwd},
    )
    assert success_change.status_code == 200

    # 4. Old password fails on next login
    old_login = await async_client.post(
        "/api/v1/auth/login", json={"email": email, "password": old_pwd}
    )
    assert old_login.status_code == 401

    # 5. New password succeeds
    new_login = await async_client.post(
        "/api/v1/auth/login", json={"email": email, "password": new_pwd}
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_foundation_workflow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify single-use password reset workflow and token hash storage."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"reset_{unique_suffix}@example.com"
    initial_pwd = "InitialPassword123!"
    new_pwd = "ResetPasswordSuccess789!"

    await async_client.post("/api/v1/auth/register", json={"email": email, "password": initial_pwd})

    # 1. Forgot password request (in test mode returns dev_reset_token)
    forgot_resp = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
    )
    assert forgot_resp.status_code == 200
    reset_token = forgot_resp.json()["details"]["dev_reset_token"]
    assert reset_token is not None

    # Verify reset token is hashed in DB
    reset_hash = hash_token(reset_token)
    stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == reset_hash)
    token_record = (await db_session.execute(stmt)).scalar_one()
    assert token_record.used_at is None

    # 2. Reset password using token
    reset_resp = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": new_pwd},
    )
    assert reset_resp.status_code == 200

    # 3. Token cannot be reused
    reuse_resp = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "YetAnotherPassword1!"},
    )
    assert reuse_resp.status_code == 401

    # 4. Login succeeds with new password
    login_resp = await async_client.post(
        "/api/v1/auth/login", json={"email": email, "password": new_pwd}
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_email_verification_foundation_workflow(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify email verification token generation, consumption, and single-use constraint."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"verify_{unique_suffix}@example.com"
    password = "VerifyPassword123!"

    await async_client.post("/api/v1/auth/register", json={"email": email, "password": password})

    # Request verification token
    resend_resp = await async_client.post(
        "/api/v1/auth/resend-verification",
        json={"email": email},
    )
    assert resend_resp.status_code == 200
    verification_token = resend_resp.json()["details"]["dev_verification_token"]

    # Verify token is hashed in DB
    token_hash = hash_token(verification_token)
    stmt = select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    token_rec = (await db_session.execute(stmt)).scalar_one()
    assert token_rec.used_at is None

    # Confirm verification
    confirm_resp = await async_client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification_token},
    )
    assert confirm_resp.status_code == 200

    # Check user is now verified
    user_stmt = select(User).where(User.email == email)
    user = (await db_session.execute(user_stmt)).scalar_one()
    assert user.is_verified is True

    # Reusing same verification token fails
    reuse_resp = await async_client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification_token},
    )
    assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_concurrent_refresh_rotation_safety(async_client: AsyncClient) -> None:
    """Verify race condition protection: concurrent refreshes do not both succeed."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"race_{unique_suffix}@example.com"
    password = "ValidPassword123!"

    await async_client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_resp = (
        await async_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    ).json()
    refresh_token = login_resp["refresh_token"]

    # Launch two simultaneous refresh calls with identical refresh token
    res1, res2 = await asyncio.gather(
        async_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}),
        async_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}),
        return_exceptions=False,
    )

    # Exactly one should succeed (200), the other must be rejected (401 due to rotation/reuse)
    status_codes = sorted([res1.status_code, res2.status_code])
    assert status_codes == [200, 401]

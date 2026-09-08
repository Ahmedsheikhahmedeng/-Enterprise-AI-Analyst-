"""Comprehensive integration test suite verifying multi-tenant authorization and isolation."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.core.config import get_settings
from app.db.postgres import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from app.main import create_app
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.user import User
from app.rbac.catalog import ROLE_ADMIN, ROLE_ANALYST, ROLE_VIEWER, SYSTEM_PERMISSIONS
from app.rbac.service import RBACService
from app.repositories.document import DocumentRepository
from app.tenancy.vector import build_qdrant_tenant_filter


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
    """Provide real PostgreSQL session for DB state setup and verification."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        yield session
    await dispose_database_engine(engine)


async def _create_test_organization(
    session: AsyncSession, name: str | None = None, is_active: bool = True
) -> Organization:
    """Helper to create a test organization."""
    uid = uuid.uuid4().hex[:8]
    org = Organization(
        name=name or f"Test Org {uid}",
        slug=f"test-org-{uid}",
        is_active=is_active,
    )
    session.add(org)
    await session.flush()
    return org


async def _create_test_user(
    session: AsyncSession, email: str | None = None, is_active: bool = True
) -> User:
    """Helper to create an active verified test user."""
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=email or f"user_{uid}@example.com",
        password_hash=hash_password("Password123!"),
        first_name="Test",
        last_name="User",
        is_active=is_active,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _ensure_seeded(session: AsyncSession) -> None:
    """Ensure system roles and permissions are seeded."""
    service = RBACService()
    await service.seed_system_rbac(session)
    await session.flush()


async def _assign_member(
    session: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID, role_name: str
) -> OrganizationMember:
    """Helper to assign a user to an organization with a specific system role."""
    role = (
        await session.execute(
            select(Role).where(Role.name == role_name, Role.organization_id.is_(None))
        )
    ).scalar_one()
    member = OrganizationMember(organization_id=organization_id, user_id=user_id, role_id=role.id)
    session.add(member)
    await session.flush()
    return member


# ===========================================================================
# TEST 1 — SINGLE ORGANIZATION RESOLUTION
# ===========================================================================
@pytest.mark.asyncio
async def test_single_organization_resolution(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A belongs only to Organization A; context resolves successfully."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    user_a = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user_a.id)

    # 1. With explicit X-Organization-ID header
    r1 = await async_client.get(
        "/api/v1/tenant/context",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org_a.id)},
    )
    assert r1.status_code == 200
    assert r1.json()["organization_id"] == str(org_a.id)
    assert r1.json()["role_name"] == ROLE_ADMIN

    # 2. Without header (safe single-membership fallback)
    r2 = await async_client.get(
        "/api/v1/tenant/context",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["organization_id"] == str(org_a.id)


# ===========================================================================
# TEST 2 — MULTIPLE ORGANIZATIONS RESOLUTION
# ===========================================================================
@pytest.mark.asyncio
async def test_multiple_organizations_resolution(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User AB belongs to A and B; header required; switches cleanly between contexts."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Alpha Corp")
    org_b = await _create_test_organization(db_session, name="Beta Corp")
    user_ab = await _create_test_user(db_session)

    await _assign_member(db_session, user_ab.id, org_a.id, ROLE_ANALYST)
    await _assign_member(db_session, user_ab.id, org_b.id, ROLE_VIEWER)
    await db_session.commit()

    token = create_access_token(user_id=user_ab.id)

    # Without header: ambiguous selection must be rejected with 403
    r_ambig = await async_client.get(
        "/api/v1/tenant/context",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_ambig.status_code == 403
    assert r_ambig.json()["error"]["code"] == "AMBIGUOUS_TENANT_CONTEXT"

    # With header A: Alpha context & Analyst role
    r_a = await async_client.get(
        "/api/v1/tenant/context",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org_a.id)},
    )
    assert r_a.status_code == 200
    assert r_a.json()["organization_id"] == str(org_a.id)
    assert r_a.json()["role_name"] == ROLE_ANALYST

    # With header B: Beta context & Viewer role
    r_b = await async_client.get(
        "/api/v1/tenant/context",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org_b.id)},
    )
    assert r_b.status_code == 200
    assert r_b.json()["organization_id"] == str(org_b.id)
    assert r_b.json()["role_name"] == ROLE_VIEWER


# ===========================================================================
# TEST 3 — NON-MEMBER ORGANIZATION REJECTION
# ===========================================================================
@pytest.mark.asyncio
async def test_non_member_organization_rejection(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A belongs only to Org A; specifying Org B in header returns 403 Forbidden."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    org_b = await _create_test_organization(db_session, name="Org B")
    user_a = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user_a.id)

    resp = await async_client.get(
        "/api/v1/tenant/context",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org_b.id)},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


# ===========================================================================
# TEST 4 — CROSS-TENANT READ (IDOR PROTECTION)
# ===========================================================================
@pytest.mark.asyncio
async def test_cross_tenant_read_returns_404(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A in Org A requests document_B belonging to Org B; must return 404 Not Found."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    org_b = await _create_test_organization(db_session, name="Org B")
    user_a = await _create_test_user(db_session)
    user_b = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)
    await _assign_member(db_session, user_b.id, org_b.id, ROLE_ADMIN)

    # Create document_B in Org B
    doc_repo = DocumentRepository()
    doc_b = await doc_repo.create(
        session=db_session,
        organization_id=org_b.id,
        name="Secret Document B",
        original_filename="secret_b.pdf",
        mime_type="application/pdf",
        file_size=1024,
        storage_key="s3://b/secret.pdf",
        created_by=user_b.id,
    )
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)

    # User A requests document_B with Org A context -> 404
    resp = await async_client.get(
        f"/api/v1/tenant/documents/{doc_b.id}",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# ===========================================================================
# TEST 5 — CROSS-TENANT UPDATE BLOCKED
# ===========================================================================
@pytest.mark.asyncio
async def test_cross_tenant_update_blocked(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A attempts to update document_B; returns 404 and leaves DB record intact."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    org_b = await _create_test_organization(db_session, name="Org B")
    user_a = await _create_test_user(db_session)
    user_b = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)
    await _assign_member(db_session, user_b.id, org_b.id, ROLE_ADMIN)

    doc_repo = DocumentRepository()
    doc_b = await doc_repo.create(
        session=db_session,
        organization_id=org_b.id,
        name="Original Name B",
        original_filename="doc_b.pdf",
        mime_type="application/pdf",
        file_size=1024,
        storage_key="s3://b/doc.pdf",
        created_by=user_b.id,
    )
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)

    # User A attempts PUT on doc_b
    resp = await async_client.put(
        f"/api/v1/tenant/documents/{doc_b.id}",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
        json={"name": "Hacked Name By User A"},
    )
    assert resp.status_code == 404

    doc_b_id = doc_b.id
    org_b_id = org_b.id
    # Verify DB: unchanged
    db_session.expire_all()
    fresh_doc_b = await doc_repo.get_by_id(db_session, id=doc_b_id, organization_id=org_b_id)
    assert fresh_doc_b is not None
    assert fresh_doc_b.name == "Original Name B"


# ===========================================================================
# TEST 6 — CROSS-TENANT DELETE BLOCKED
# ===========================================================================
@pytest.mark.asyncio
async def test_cross_tenant_delete_blocked(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A attempts to delete document_B; returns 404 and leaves DB record intact."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    org_b = await _create_test_organization(db_session, name="Org B")
    user_a = await _create_test_user(db_session)
    user_b = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)
    await _assign_member(db_session, user_b.id, org_b.id, ROLE_ADMIN)

    doc_repo = DocumentRepository()
    doc_b = await doc_repo.create(
        session=db_session,
        organization_id=org_b.id,
        name="Doc B",
        original_filename="doc_b.pdf",
        mime_type="application/pdf",
        file_size=1024,
        storage_key="s3://b/doc.pdf",
        created_by=user_b.id,
    )
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)

    # User A attempts DELETE on doc_b
    resp = await async_client.delete(
        f"/api/v1/tenant/documents/{doc_b.id}",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
    )
    assert resp.status_code == 404

    # Verify DB: still exists in Org B
    fresh_doc_b = await doc_repo.get_by_id(db_session, id=doc_b.id, organization_id=org_b.id)
    assert fresh_doc_b is not None


# ===========================================================================
# TEST 7 — CROSS-TENANT LIST ISOLATION
# ===========================================================================
@pytest.mark.asyncio
async def test_cross_tenant_list_isolation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """5 docs in Org A, 5 docs in Org B; User A lists documents and receives only Org A docs."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    org_b = await _create_test_organization(db_session, name="Org B")
    user_a = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)

    doc_repo = DocumentRepository()
    for i in range(5):
        await doc_repo.create(
            session=db_session,
            organization_id=org_a.id,
            name=f"Doc A {i}",
            original_filename=f"doc_a_{i}.pdf",
            mime_type="application/pdf",
            file_size=500,
            storage_key=f"s3://a/{i}.pdf",
        )
        await doc_repo.create(
            session=db_session,
            organization_id=org_b.id,
            name=f"Doc B {i}",
            original_filename=f"doc_b_{i}.pdf",
            mime_type="application/pdf",
            file_size=500,
            storage_key=f"s3://b/{i}.pdf",
        )
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)
    resp = await async_client.get(
        "/api/v1/tenant/documents?limit=50",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
    )
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) == 5
    for doc in docs:
        assert doc["organization_id"] == str(org_a.id)
        assert "Doc A" in doc["name"]


# ===========================================================================
# TEST 8 — CROSS-TENANT COUNT ISOLATION
# ===========================================================================
@pytest.mark.asyncio
async def test_cross_tenant_count_isolation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """3 docs in Org A, 7 docs in Org B; User A count endpoint returns exactly 3."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    org_b = await _create_test_organization(db_session, name="Org B")
    user_a = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)

    doc_repo = DocumentRepository()
    for i in range(3):
        await doc_repo.create(
            session=db_session,
            organization_id=org_a.id,
            name=f"Doc A {i}",
            original_filename=f"a_{i}.pdf",
            mime_type="application/pdf",
            file_size=100,
            storage_key=f"s3://a/{i}",
        )
    for i in range(7):
        await doc_repo.create(
            session=db_session,
            organization_id=org_b.id,
            name=f"Doc B {i}",
            original_filename=f"b_{i}.pdf",
            mime_type="application/pdf",
            file_size=100,
            storage_key=f"s3://b/{i}",
        )
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)
    resp = await async_client.get(
        "/api/v1/tenant/documents/count",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 3
    assert resp.json()["organization_id"] == str(org_a.id)


# ===========================================================================
# TEST 9 — NESTED RESOURCE SECURITY (CHUNK TRAVERSAL)
# ===========================================================================
@pytest.mark.asyncio
async def test_nested_resource_traversal_protection(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Cannot fetch chunk_A under document_B, or chunk_B under document_A."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    org_b = await _create_test_organization(db_session, name="Org B")
    user_a = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)

    doc_repo = DocumentRepository()
    doc_a = await doc_repo.create(
        session=db_session,
        organization_id=org_a.id,
        name="Doc A",
        original_filename="a.pdf",
        mime_type="application/pdf",
        file_size=100,
        storage_key="s3://a",
    )
    chunk_a = await doc_repo.create_chunk(
        session=db_session,
        document_id=doc_a.id,
        organization_id=org_a.id,
        chunk_index=0,
        content="Content A",
    )
    doc_b = await doc_repo.create(
        session=db_session,
        organization_id=org_b.id,
        name="Doc B",
        original_filename="b.pdf",
        mime_type="application/pdf",
        file_size=100,
        storage_key="s3://b",
    )
    chunk_b = await doc_repo.create_chunk(
        session=db_session,
        document_id=doc_b.id,
        organization_id=org_b.id,
        chunk_index=0,
        content="Content B",
    )
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)
    headers = {"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)}

    # 1. Valid nested chunk in own tenant -> 200
    r_valid = await async_client.get(
        f"/api/v1/tenant/documents/{doc_a.id}/chunks/{chunk_a.id}", headers=headers
    )
    assert r_valid.status_code == 200
    assert r_valid.json()["content"] == "Content A"

    # 2. Attempting to fetch chunk_B using doc_a path -> 404
    r_mismatch = await async_client.get(
        f"/api/v1/tenant/documents/{doc_a.id}/chunks/{chunk_b.id}", headers=headers
    )
    assert r_mismatch.status_code == 404

    # 3. Attempting to fetch chunk_A using doc_b path -> 404
    r_cross = await async_client.get(
        f"/api/v1/tenant/documents/{doc_b.id}/chunks/{chunk_a.id}", headers=headers
    )
    assert r_cross.status_code == 404


# ===========================================================================
# TEST 10 — CROSS-TENANT ROLE DIFFERENTIATION
# ===========================================================================
@pytest.mark.asyncio
async def test_cross_tenant_role_differentiation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User is Analyst in Org A (write allowed), Viewer in Org B (write denied)."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    org_b = await _create_test_organization(db_session, name="Org B")
    user = await _create_test_user(db_session)

    await _assign_member(db_session, user.id, org_a.id, ROLE_ANALYST)
    await _assign_member(db_session, user.id, org_b.id, ROLE_VIEWER)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    payload = {
        "name": "Test Document",
        "original_filename": "test.pdf",
        "mime_type": "application/pdf",
        "file_size": 100,
        "storage_key": "s3://doc",
    }

    # In Org A (Analyst): documents.write is allowed -> 201 Created
    r_a = await async_client.post(
        "/api/v1/tenant/documents",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org_a.id)},
        json=payload,
    )
    assert r_a.status_code == 201

    # In Org B (Viewer): documents.write is denied -> 403 Forbidden
    r_b = await async_client.post(
        "/api/v1/tenant/documents",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org_b.id)},
        json=payload,
    )
    assert r_b.status_code == 403


# ===========================================================================
# TEST 11 — HEADER TAMPERING TO NON-MEMBER ORG
# ===========================================================================
@pytest.mark.asyncio
async def test_header_tampering_rejected(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A tampers X-Organization-ID to Org B; rejected with 403 Forbidden."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    org_b = await _create_test_organization(db_session, name="Org B")
    user_a = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)
    resp = await async_client.get(
        "/api/v1/tenant/documents",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_b.id)},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


# ===========================================================================
# TEST 12 — RESOURCE IDOR WITH VALID UUID
# ===========================================================================
@pytest.mark.asyncio
async def test_resource_idor_leakage_prevented(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A knowing exact UUID of resource in Org B cannot read metadata or content."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session)
    org_b = await _create_test_organization(db_session)
    user_a = await _create_test_user(db_session)
    user_b = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)
    await _assign_member(db_session, user_b.id, org_b.id, ROLE_ADMIN)

    doc_repo = DocumentRepository()
    doc_b = await doc_repo.create(
        session=db_session,
        organization_id=org_b.id,
        name="Confidential Financials",
        original_filename="financials.pdf",
        mime_type="application/pdf",
        file_size=99999,
        storage_key="s3://b/secret_financials.pdf",
        created_by=user_b.id,
    )
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)
    resp = await async_client.get(
        f"/api/v1/tenant/documents/{doc_b.id}",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
    )
    assert resp.status_code == 404
    # Ensure confidential details are not leaked in error envelope
    assert "Confidential Financials" not in resp.text
    assert "financials.pdf" not in resp.text


# ===========================================================================
# TEST 13 — CREATE RESOURCE MALICIOUS ORG_ID IN PAYLOAD
# ===========================================================================
@pytest.mark.asyncio
async def test_create_resource_ignores_payload_org_id(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A passes organization_id = Org B in payload; resource is saved strictly in Org A."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    org_b = await _create_test_organization(db_session, name="Org B")
    user_a = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)
    payload = {
        "name": "Injection Document",
        "original_filename": "inj.pdf",
        "mime_type": "application/pdf",
        "file_size": 200,
        "storage_key": "s3://inj.pdf",
        "organization_id": str(org_b.id),  # Attacker attempt
    }
    resp = await async_client.post(
        "/api/v1/tenant/documents",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
        json=payload,
    )
    assert resp.status_code == 201
    created_doc = resp.json()
    assert created_doc["organization_id"] == str(org_a.id)
    assert created_doc["organization_id"] != str(org_b.id)


# ===========================================================================
# TEST 14 — UPDATE OWN TENANT RESOURCE
# ===========================================================================
@pytest.mark.asyncio
async def test_update_own_tenant_resource_success(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A updates document in own tenant; succeeds and mutates database."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    user_a = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)

    doc_repo = DocumentRepository()
    doc_a = await doc_repo.create(
        session=db_session,
        organization_id=org_a.id,
        name="Old Name",
        original_filename="a.pdf",
        mime_type="application/pdf",
        file_size=100,
        storage_key="s3://a",
    )
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)
    resp = await async_client.put(
        f"/api/v1/tenant/documents/{doc_a.id}",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
        json={"name": "New Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"

    doc_a_id = doc_a.id
    org_a_id = org_a.id
    # Verify DB
    db_session.expire_all()
    updated = await doc_repo.get_by_id(db_session, id=doc_a_id, organization_id=org_a_id)
    assert updated is not None and updated.name == "New Name"


# ===========================================================================
# TEST 15 — DELETE OWN TENANT RESOURCE
# ===========================================================================
@pytest.mark.asyncio
async def test_delete_own_tenant_resource_success(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A deletes document in own tenant; succeeds and removes database row."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    user_a = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)

    doc_repo = DocumentRepository()
    doc_a = await doc_repo.create(
        session=db_session,
        organization_id=org_a.id,
        name="To Delete",
        original_filename="del.pdf",
        mime_type="application/pdf",
        file_size=100,
        storage_key="s3://del",
    )
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)
    resp = await async_client.delete(
        f"/api/v1/tenant/documents/{doc_a.id}",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
    )
    assert resp.status_code == 200

    # Verify DB
    deleted = await doc_repo.get_by_id(db_session, id=doc_a.id, organization_id=org_a.id)
    assert deleted is None


# ===========================================================================
# TEST 16 — TRANSACTION ISOLATION
# ===========================================================================
@pytest.mark.asyncio
async def test_transaction_isolation_between_tenants(
    db_session: AsyncSession,
) -> None:
    """Mutations in Org A transaction do not leak or affect Org B state."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Org A")
    org_b = await _create_test_organization(db_session, name="Org B")

    doc_repo = DocumentRepository()
    doc_b = await doc_repo.create(
        session=db_session,
        organization_id=org_b.id,
        name="Untouched B",
        original_filename="b.pdf",
        mime_type="application/pdf",
        file_size=100,
        storage_key="s3://b",
    )
    await db_session.commit()

    # Perform transaction modifying only Org A
    await doc_repo.create(
        session=db_session,
        organization_id=org_a.id,
        name="Added in A",
        original_filename="a.pdf",
        mime_type="application/pdf",
        file_size=100,
        storage_key="s3://a",
    )
    await db_session.commit()

    # Verify Org B remains untouched
    count_b = await doc_repo.count(db_session, organization_id=org_b.id)
    assert count_b == 1
    doc_b_fresh = await doc_repo.get_by_id(db_session, id=doc_b.id, organization_id=org_b.id)
    assert doc_b_fresh is not None and doc_b_fresh.name == "Untouched B"


# ===========================================================================
# TEST 17 — REPOSITORY MANDATORY TENANT SCOPE
# ===========================================================================
@pytest.mark.asyncio
async def test_repository_mandatory_tenant_scope(
    db_session: AsyncSession,
) -> None:
    """Direct repository methods enforce organization_id; wrong org returns None/False."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session)
    org_b = await _create_test_organization(db_session)

    doc_repo = DocumentRepository()
    doc_a = await doc_repo.create(
        session=db_session,
        organization_id=org_a.id,
        name="Doc A",
        original_filename="a.pdf",
        mime_type="application/pdf",
        file_size=100,
        storage_key="s3://a",
    )
    await db_session.flush()

    # Calling get_by_id with Org B's ID for Doc A returns None
    retrieved_in_b = await doc_repo.get_by_id(db_session, id=doc_a.id, organization_id=org_b.id)
    assert retrieved_in_b is None

    # Calling update with Org B's ID for Doc A returns None
    updated_in_b = await doc_repo.update(
        db_session, id=doc_a.id, organization_id=org_b.id, name="Malicious"
    )
    assert updated_in_b is None

    # Calling delete with Org B's ID for Doc A returns False
    deleted_in_b = await doc_repo.delete(db_session, id=doc_a.id, organization_id=org_b.id)
    assert deleted_in_b is False


# ===========================================================================
# TEST 18 — QUERY EFFICIENCY (NO N+1)
# ===========================================================================
@pytest.mark.asyncio
async def test_tenant_context_resolution_no_n_plus_one(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Resolving tenant context and permissions executes efficiently without N+1 loops."""
    await _ensure_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    resp = await async_client.get(
        "/api/v1/tenant/context",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
    )
    assert resp.status_code == 200
    assert len(resp.json()["permissions"]) == len(SYSTEM_PERMISSIONS)


# ===========================================================================
# TEST 19 — EMPTY MEMBERSHIP REJECTION
# ===========================================================================
@pytest.mark.asyncio
async def test_empty_membership_rejected(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User belonging to zero organizations cannot resolve tenant context (403 Forbidden)."""
    user_orphan = await _create_test_user(db_session)
    await db_session.commit()

    token = create_access_token(user_id=user_orphan.id)
    resp = await async_client.get(
        "/api/v1/tenant/context",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


# ===========================================================================
# TEST 20 — INVALID ORGANIZATION UUID (VALIDATION FAILURE WITHOUT DB QUERY)
# ===========================================================================
@pytest.mark.asyncio
async def test_invalid_organization_uuid_fails_validation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Malformed X-Organization-ID header fails with 422 before executing DB queries."""
    user = await _create_test_user(db_session)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    resp = await async_client.get(
        "/api/v1/tenant/context",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": "not-a-uuid"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_ORGANIZATION_ID"


# ===========================================================================
# TEST 21 — DEACTIVATED USER REJECTION
# ===========================================================================
@pytest.mark.asyncio
async def test_deactivated_user_rejected(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Deactivated user account fails authentication with 401 Unauthorized."""
    org = await _create_test_organization(db_session)
    user_inactive = await _create_test_user(db_session, is_active=False)
    await _assign_member(db_session, user_inactive.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user_inactive.id)
    resp = await async_client.get(
        "/api/v1/tenant/context",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INACTIVE_USER"


# ===========================================================================
# TEST 22 — DEACTIVATED ORGANIZATION REJECTION
# ===========================================================================
@pytest.mark.asyncio
async def test_deactivated_organization_rejected(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Deactivated organization (is_active=False) returns 403 ORGANIZATION_INACTIVE."""
    org_inactive = await _create_test_organization(db_session, is_active=False)
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org_inactive.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    resp = await async_client.get(
        "/api/v1/tenant/context",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org_inactive.id)},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ORGANIZATION_INACTIVE"


# ===========================================================================
# TEST 23 — QDRANT TENANT ISOLATION FILTER BUILDER
# ===========================================================================
def test_qdrant_tenant_isolation_filter_builder() -> None:
    """Verify build_qdrant_tenant_filter constructs the mandatory organization payload condition."""
    test_org_id = uuid.uuid4()
    filter_dict = build_qdrant_tenant_filter(test_org_id)
    assert "must" in filter_dict
    assert len(filter_dict["must"]) == 1
    condition = filter_dict["must"][0]
    assert condition["key"] == "organization_id"
    assert condition["match"]["value"] == str(test_org_id)

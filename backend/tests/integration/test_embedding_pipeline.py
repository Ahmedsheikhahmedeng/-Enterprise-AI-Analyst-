"""Integration tests for Task 10 Embeddings & Embedding Pipeline.

Covers:
- End-to-end document embedding flow (upload -> ingest -> chunk -> embed).
- DB persistence in document_chunk_embeddings.
- Idempotent re-embedding and force re-embedding.
- Tenant isolation (Org B cannot embed or read Org A embeddings).
- RBAC enforcement (Viewer gets 403 on POST, 200 on GET).
- Cascade deletion on document delete.
"""

import io
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
from app.models.document import Document, DocumentChunkEmbedding
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.user import User
from app.rbac.catalog import ROLE_ADMIN, ROLE_ANALYST, ROLE_VIEWER
from app.rbac.service import RBACService


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient wired to FastAPI app with PostgreSQL database state."""
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


async def _create_test_organization(session: AsyncSession, name: str | None = None) -> Organization:
    uid = uuid.uuid4().hex[:8]
    org = Organization(
        name=name or f"Emb Org {uid}",
        slug=f"emb-org-{uid}",
        is_active=True,
    )
    session.add(org)
    await session.flush()
    return org


async def _create_test_user(session: AsyncSession, email: str | None = None) -> User:
    uid = uuid.uuid4().hex[:8]
    if email:
        prefix, domain = email.split("@", 1)
        unique_email = f"{prefix}_{uid}@{domain}"
    else:
        unique_email = f"emb_user_{uid}@example.com"
    user = User(
        email=unique_email,
        password_hash=hash_password("Password123!"),
        first_name="Emb",
        last_name="Tester",
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _ensure_rbac_seeded(session: AsyncSession) -> None:
    service = RBACService()
    await service.seed_system_rbac(session)
    await session.flush()


async def _assign_member(
    session: AsyncSession,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    role_name: str,
) -> None:
    role = (
        await session.execute(
            select(Role).where(
                Role.name == role_name,
                Role.organization_id.is_(None),
            )
        )
    ).scalar_one()
    member = OrganizationMember(
        organization_id=org_id,
        user_id=user_id,
        role_id=role.id,
    )
    session.add(member)
    await session.flush()


async def _create_processed_document(
    async_client: AsyncClient,
    session: AsyncSession,
    org: Organization,
    user: User,
) -> uuid.UUID:
    """Helper creating an uploaded, parsed, and chunked document."""
    token = create_access_token(user_id=user.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    text_content = (
        "# Q4 2025 Financial Performance\n\n"
        "## Revenue\n\n"
        "Revenue grew by 24% year-over-year to $120 million in Q4 2025.\n\n"
        "## Expenses and Operating Margin\n\n"
        "Operating expenses remained tightly controlled at $45 million.\n"
    )
    upload_res = await async_client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("report.txt", io.BytesIO(text_content.encode("utf-8")), "text/plain")},
    )
    assert upload_res.status_code == 201
    doc_id = uuid.UUID(upload_res.json()["id"])

    # Ingest synchronously
    ingest_res = await async_client.post(
        f"/api/v1/documents/{doc_id}/ingest?sync=true",
        headers=headers,
    )
    assert ingest_res.status_code == 200

    # Chunk synchronously
    chunk_res = await async_client.post(
        f"/api/v1/documents/{doc_id}/chunks?sync=true",
        headers=headers,
    )
    assert chunk_res.status_code == 200
    assert chunk_res.json()["total_chunks"] > 0

    return doc_id


# ==========================================
# Integration Tests
# ==========================================


@pytest.mark.asyncio
async def test_end_to_end_embedding_pipeline(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test full document embedding pipeline via REST API and PostgreSQL persistence."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session)
    admin = await _create_test_user(db_session)
    await _assign_member(db_session, admin.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    doc_id = await _create_processed_document(async_client, db_session, org, admin)

    token = create_access_token(user_id=admin.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    # 1. Trigger Embeddings Synchronously
    res = await async_client.post(
        f"/api/v1/documents/{doc_id}/embeddings?sync=true",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["document_id"] == str(doc_id)
    assert data["organization_id"] == str(org.id)
    assert data["total_embeddings"] > 0
    assert data["completed_count"] == data["total_embeddings"]
    assert data["failed_count"] == 0
    assert data["dimensions"] > 0

    # 2. Check Database Records in document_chunk_embeddings
    stmt = select(DocumentChunkEmbedding).where(
        DocumentChunkEmbedding.document_id == doc_id,
        DocumentChunkEmbedding.organization_id == org.id,
    )
    records = (await db_session.execute(stmt)).scalars().all()
    assert len(records) == data["total_embeddings"]
    for r in records:
        assert r.status == "completed"
        assert r.failure_reason is None
        assert len(r.embedding_input_hash) == 64
        assert r.token_count > 0

    # 3. Check Document Status
    doc = (await db_session.execute(select(Document).where(Document.id == doc_id))).scalar_one()
    assert doc.status == "embedded"
    assert doc.metadata_ is not None
    assert doc.metadata_["embedding_count"] == len(records)

    # 4. List Embeddings via GET API
    list_res = await async_client.get(
        f"/api/v1/documents/{doc_id}/embeddings",
        headers=headers,
    )
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == len(records)
    assert len(list_data["items"]) == len(records)


@pytest.mark.asyncio
async def test_idempotent_reembedding(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Re-embedding without force returns existing embeddings; force=True regenerates cleanly."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session)
    admin = await _create_test_user(db_session)
    await _assign_member(db_session, admin.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    doc_id = await _create_processed_document(async_client, db_session, org, admin)
    token = create_access_token(user_id=admin.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    # Initial run
    res1 = await async_client.post(
        f"/api/v1/documents/{doc_id}/embeddings?sync=true",
        headers=headers,
    )
    assert res1.status_code == 200
    total1 = res1.json()["total_embeddings"]

    # Idempotent second run (no force)
    res2 = await async_client.post(
        f"/api/v1/documents/{doc_id}/embeddings?sync=true&force=false",
        headers=headers,
    )
    assert res2.status_code == 200
    assert res2.json()["completed_count"] == total1
    assert res2.json()["cache_hits"] == total1

    # Force re-embedding
    res3 = await async_client.post(
        f"/api/v1/documents/{doc_id}/embeddings?sync=true&force=true",
        headers=headers,
    )
    assert res3.status_code == 200
    assert res3.json()["completed_count"] == total1

    # Verify no duplicate rows in DB
    stmt = select(DocumentChunkEmbedding).where(
        DocumentChunkEmbedding.document_id == doc_id,
        DocumentChunkEmbedding.organization_id == org.id,
    )
    records = (await db_session.execute(stmt)).scalars().all()
    assert len(records) == total1


@pytest.mark.asyncio
async def test_tenant_isolation_embeddings(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Tenant B user cannot generate or read embeddings for Tenant A's document."""
    await _ensure_rbac_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Tenant A")
    admin_a = await _create_test_user(db_session, email="admin_a@tenanta.com")
    await _assign_member(db_session, admin_a.id, org_a.id, ROLE_ADMIN)

    org_b = await _create_test_organization(db_session, name="Tenant B")
    user_b = await _create_test_user(db_session, email="user_b@tenantb.com")
    await _assign_member(db_session, user_b.id, org_b.id, ROLE_ANALYST)
    await db_session.commit()

    doc_a_id = await _create_processed_document(async_client, db_session, org_a, admin_a)

    token_b = create_access_token(user_id=user_b.id)
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Organization-ID": str(org_b.id),
    }

    # Org B attempts to trigger embeddings on Org A's document -> 404 NOT FOUND
    res_trigger = await async_client.post(
        f"/api/v1/documents/{doc_a_id}/embeddings?sync=true",
        headers=headers_b,
    )
    assert res_trigger.status_code == 404

    # Org B attempts to list embeddings of Org A's document -> 404 NOT FOUND
    res_list = await async_client.get(
        f"/api/v1/documents/{doc_a_id}/embeddings",
        headers=headers_b,
    )
    assert res_list.status_code == 404


@pytest.mark.asyncio
async def test_rbac_enforcement_embeddings(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Viewer can read document embeddings but cannot trigger embedding generation.

    Expects 403 Forbidden on write, 200 OK on read.
    """

    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session)
    admin = await _create_test_user(db_session)
    viewer = await _create_test_user(db_session)
    await _assign_member(db_session, admin.id, org.id, ROLE_ADMIN)
    await _assign_member(db_session, viewer.id, org.id, ROLE_VIEWER)
    await db_session.commit()

    doc_id = await _create_processed_document(async_client, db_session, org, admin)

    # Embed as admin
    token_admin = create_access_token(user_id=admin.id)
    headers_admin = {
        "Authorization": f"Bearer {token_admin}",
        "X-Organization-ID": str(org.id),
    }
    await async_client.post(
        f"/api/v1/documents/{doc_id}/embeddings?sync=true",
        headers=headers_admin,
    )

    token_viewer = create_access_token(user_id=viewer.id)
    headers_viewer = {
        "Authorization": f"Bearer {token_viewer}",
        "X-Organization-ID": str(org.id),
    }

    # Viewer triggers embedding -> 403 FORBIDDEN
    res_trigger = await async_client.post(
        f"/api/v1/documents/{doc_id}/embeddings?sync=true",
        headers=headers_viewer,
    )
    assert res_trigger.status_code == 403

    # Viewer reads embeddings -> 200 OK
    res_read = await async_client.get(
        f"/api/v1/documents/{doc_id}/embeddings",
        headers=headers_viewer,
    )
    assert res_read.status_code == 200
    assert res_read.json()["total"] > 0


@pytest.mark.asyncio
async def test_cascade_delete_embeddings(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Deleting a document cascades and removes all chunk embedding records."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session)
    admin = await _create_test_user(db_session)
    await _assign_member(db_session, admin.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    doc_id = await _create_processed_document(async_client, db_session, org, admin)
    token = create_access_token(user_id=admin.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    # Embed document
    emb_res = await async_client.post(
        f"/api/v1/documents/{doc_id}/embeddings?sync=true",
        headers=headers,
    )
    assert emb_res.status_code == 200

    # Verify embeddings exist in DB
    stmt = select(DocumentChunkEmbedding).where(
        DocumentChunkEmbedding.document_id == doc_id,
    )
    records_before = (await db_session.execute(stmt)).scalars().all()
    assert len(records_before) > 0

    # Delete document via API (soft-delete)
    del_res = await async_client.delete(
        f"/api/v1/documents/{doc_id}",
        headers=headers,
    )
    assert del_res.status_code == 200

    # Verify querying embeddings via API returns 404 for deleted document
    get_res = await async_client.get(
        f"/api/v1/documents/{doc_id}/embeddings",
        headers=headers,
    )
    assert get_res.status_code == 404

    # Verify database ON DELETE CASCADE on physical document deletion
    doc = (await db_session.execute(select(Document).where(Document.id == doc_id))).scalar_one()
    await db_session.delete(doc)
    await db_session.commit()

    records_after = (await db_session.execute(stmt)).scalars().all()
    assert len(records_after) == 0

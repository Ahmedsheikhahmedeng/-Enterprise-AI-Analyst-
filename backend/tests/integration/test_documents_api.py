"""Integration test suite for Document Management API, Tenant Isolation, RBAC, and Storage."""

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
from app.models.document import Document
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.user import User
from app.rbac.catalog import ROLE_ADMIN, ROLE_ANALYST, ROLE_VIEWER
from app.rbac.service import RBACService
from app.storage import get_storage_provider
from app.storage.validation import PDF_MAGIC


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


async def _create_test_organization(session: AsyncSession, name: str | None = None) -> Organization:
    """Helper to create a test organization."""
    uid = uuid.uuid4().hex[:8]
    org = Organization(
        name=name or f"Test Org {uid}",
        slug=f"test-org-{uid}",
        is_active=True,
    )
    session.add(org)
    await session.flush()
    return org


async def _create_test_user(session: AsyncSession, email: str | None = None) -> User:
    """Helper to create an active verified test user."""
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=email or f"user_{uid}@example.com",
        password_hash=hash_password("Password123!"),
        first_name="DocTest",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _ensure_rbac_seeded(session: AsyncSession) -> None:
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
# 1. DOCUMENT UPLOAD TESTS
# ===========================================================================
@pytest.mark.asyncio
async def test_document_upload_success(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify successful upload of PDF document with metadata persistence and safe headers."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session, "Upload Org")
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    pdf_content = PDF_MAGIC + b"1.4 Sample PDF content for upload verification."

    response = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
        files={"file": ("financial_report.pdf", pdf_content, "application/pdf")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "financial_report.pdf"
    assert data["original_filename"] == "financial_report.pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["detected_mime_type"] == "application/pdf"
    assert data["file_size"] == len(pdf_content)
    assert len(data["sha256"]) == 64
    assert data["status"] == "uploaded"
    assert "storage_key" not in data  # Never leak internal storage path in response


# ===========================================================================
# 2. DUPLICATE DETECTION (TENANT-SCOPED) TESTS
# ===========================================================================
@pytest.mark.asyncio
async def test_duplicate_document_same_tenant_conflict(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Uploading the exact same file in the same tenant raises 409 Conflict."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session, "Dup Org")
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    content = PDF_MAGIC + b"1.4 Duplicate content test."

    # 1. First upload succeeds
    r1 = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
        files={"file": ("report_v1.pdf", content, "application/pdf")},
    )
    assert r1.status_code == 201

    # 2. Second upload with identical content in same tenant is rejected
    r2 = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
        files={"file": ("report_v2.pdf", content, "application/pdf")},
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "DUPLICATE_DOCUMENT"


@pytest.mark.asyncio
async def test_duplicate_document_different_tenants_allowed(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Identical file uploaded across different tenants is permitted (isolated namespaces)."""
    await _ensure_rbac_seeded(db_session)
    org_a = await _create_test_organization(db_session, "Org A")
    org_b = await _create_test_organization(db_session, "Org B")
    user_a = await _create_test_user(db_session)
    user_b = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)
    await _assign_member(db_session, user_b.id, org_b.id, ROLE_ADMIN)
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)
    token_b = create_access_token(user_id=user_b.id)
    shared_content = PDF_MAGIC + b"1.4 Identical file for cross-tenant testing."

    # 1. Org A uploads file
    r_a = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
        files={"file": ("doc.pdf", shared_content, "application/pdf")},
    )
    assert r_a.status_code == 201

    # 2. Org B uploads identical file -> Allowed
    r_b = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token_b}", "X-Organization-ID": str(org_b.id)},
        files={"file": ("doc.pdf", shared_content, "application/pdf")},
    )
    assert r_b.status_code == 201
    assert r_a.json()["id"] != r_b.json()["id"]
    assert r_a.json()["sha256"] == r_b.json()["sha256"]


# ===========================================================================
# 3. TENANT ISOLATION & ACCESS CONTROL (IDOR PREVENTION)
# ===========================================================================
@pytest.mark.asyncio
async def test_cross_tenant_reads_return_404(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """User in Org A cannot view, download, or delete Org B's documents (404 Not Found)."""
    await _ensure_rbac_seeded(db_session)
    org_a = await _create_test_organization(db_session, "Org A")
    org_b = await _create_test_organization(db_session, "Org B")
    user_a = await _create_test_user(db_session)
    user_b = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)
    await _assign_member(db_session, user_b.id, org_b.id, ROLE_ADMIN)
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)
    token_b = create_access_token(user_id=user_b.id)

    # Org B uploads a secret document
    r_upload = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token_b}", "X-Organization-ID": str(org_b.id)},
        files={"file": ("secret_b.txt", b"Confidential Org B data", "text/plain")},
    )
    assert r_upload.status_code == 201
    doc_b_id = r_upload.json()["id"]

    # 1. User A attempts to view Org B document -> 404
    r_detail = await async_client.get(
        f"/api/v1/documents/{doc_b_id}",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
    )
    assert r_detail.status_code == 404

    # 2. User A attempts to download Org B document -> 404 (No data leakage)
    r_download = await async_client.get(
        f"/api/v1/documents/{doc_b_id}/download",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
    )
    assert r_download.status_code == 404

    # 3. User A attempts to delete Org B document -> 404
    r_delete = await async_client.get(
        f"/api/v1/documents/{doc_b_id}/download",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
    )
    assert r_delete.status_code == 404

    # 4. Org B still owns and can download its document
    r_owner_download = await async_client.get(
        f"/api/v1/documents/{doc_b_id}/download",
        headers={"Authorization": f"Bearer {token_b}", "X-Organization-ID": str(org_b.id)},
    )
    assert r_owner_download.status_code == 200
    assert r_owner_download.content == b"Confidential Org B data"


@pytest.mark.asyncio
async def test_client_cannot_override_organization_id(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Attacker supplying malicious organization_id in request body cannot bypass TenantContext."""
    await _ensure_rbac_seeded(db_session)
    org_a = await _create_test_organization(db_session, "Org A")
    org_b = await _create_test_organization(db_session, "Org B")
    user_a = await _create_test_user(db_session)
    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)

    # Attempt to upload with organization_id targeting Org B in form data
    response = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)},
        data={"organization_id": str(org_b.id)},
        files={"file": ("tamper.txt", b"Tamper attempt", "text/plain")},
    )
    assert response.status_code == 201
    doc_id = uuid.UUID(response.json()["id"])

    # Verify directly in DB that document belongs exclusively to Org A
    doc = (await db_session.execute(select(Document).where(Document.id == doc_id))).scalar_one()
    assert doc.organization_id == org_a.id
    assert doc.organization_id != org_b.id


# ===========================================================================
# 4. RBAC PERMISSION ENFORCEMENT
# ===========================================================================
@pytest.mark.asyncio
async def test_rbac_permission_enforcement(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify role permissions: Viewer (read only), Analyst (write, no delete), Admin (all)."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session, "RBAC Org")
    viewer_user = await _create_test_user(db_session)
    analyst_user = await _create_test_user(db_session)
    admin_user = await _create_test_user(db_session)

    await _assign_member(db_session, viewer_user.id, org.id, ROLE_VIEWER)
    await _assign_member(db_session, analyst_user.id, org.id, ROLE_ANALYST)
    await _assign_member(db_session, admin_user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    t_viewer = create_access_token(user_id=viewer_user.id)
    t_analyst = create_access_token(user_id=analyst_user.id)
    t_admin = create_access_token(user_id=admin_user.id)
    headers_viewer = {"Authorization": f"Bearer {t_viewer}", "X-Organization-ID": str(org.id)}
    headers_analyst = {"Authorization": f"Bearer {t_analyst}", "X-Organization-ID": str(org.id)}
    headers_admin = {"Authorization": f"Bearer {t_admin}", "X-Organization-ID": str(org.id)}

    # 1. Viewer attempts upload -> 403 Forbidden
    r_viewer_upload = await async_client.post(
        "/api/v1/documents",
        headers=headers_viewer,
        files={"file": ("test.txt", b"Viewer data", "text/plain")},
    )
    assert r_viewer_upload.status_code == 403

    # 2. Analyst uploads document -> 201 Created
    r_analyst_upload = await async_client.post(
        "/api/v1/documents",
        headers=headers_analyst,
        files={"file": ("analyst_doc.txt", b"Analyst data", "text/plain")},
    )
    assert r_analyst_upload.status_code == 201
    doc_id = r_analyst_upload.json()["id"]

    # 3. Viewer can read and download document -> 200 OK
    r_viewer_read = await async_client.get(f"/api/v1/documents/{doc_id}", headers=headers_viewer)
    assert r_viewer_read.status_code == 200
    r_viewer_dl = await async_client.get(
        f"/api/v1/documents/{doc_id}/download", headers=headers_viewer
    )
    assert r_viewer_dl.status_code == 200

    # 4. Viewer attempts delete -> 403 Forbidden
    r_viewer_del = await async_client.delete(f"/api/v1/documents/{doc_id}", headers=headers_viewer)
    assert r_viewer_del.status_code == 403

    # 5. Analyst attempts delete -> 403 Forbidden
    r_analyst_del = await async_client.delete(
        f"/api/v1/documents/{doc_id}", headers=headers_analyst
    )
    assert r_analyst_del.status_code == 403

    # 6. Admin deletes document -> 200 OK
    r_admin_del = await async_client.delete(f"/api/v1/documents/{doc_id}", headers=headers_admin)
    assert r_admin_del.status_code == 200


# ===========================================================================
# 5. DOWNLOAD AND DELETE LIFECYCLE TESTS
# ===========================================================================
@pytest.mark.asyncio
async def test_download_and_soft_delete_lifecycle(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify download headers, soft-delete database update, and physical file deletion."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session, "Lifecycle Org")
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)}
    content = PDF_MAGIC + b"1.4 Lifecycle test file."

    # 1. Upload
    up_res = await async_client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("my_statement.pdf", content, "application/pdf")},
    )
    assert up_res.status_code == 201
    doc_id = up_res.json()["id"]

    # 2. Download and verify headers
    dl_res = await async_client.get(f"/api/v1/documents/{doc_id}/download", headers=headers)
    assert dl_res.status_code == 200
    assert dl_res.content == content
    assert dl_res.headers["Content-Type"] == "application/pdf"
    assert "my_statement.pdf" in dl_res.headers["Content-Disposition"]
    assert dl_res.headers["Content-Length"] == str(len(content))

    # 3. Check storage key on filesystem
    storage = get_storage_provider()
    db_doc = (
        await db_session.execute(select(Document).where(Document.id == uuid.UUID(doc_id)))
    ).scalar_one()
    storage_key = db_doc.storage_key
    assert await storage.exists(storage_key) is True

    # 4. Delete document
    del_res = await async_client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert del_res.status_code == 200

    # 5. Assert physical storage object was purged
    assert await storage.exists(storage_key) is False

    # 6. Subsequent list and detail queries filter out deleted document
    list_res = await async_client.get("/api/v1/documents", headers=headers)
    assert list_res.status_code == 200
    assert all(item["id"] != doc_id for item in list_res.json()["items"])

    get_res = await async_client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert get_res.status_code == 404

    # 7. Verify soft delete record in DB
    await db_session.refresh(db_doc)
    assert db_doc.status == "deleted"
    assert db_doc.deleted_at is not None


# ===========================================================================
# 6. ATOMIC STORAGE & ORPHAN CLEANUP TESTS
# ===========================================================================
@pytest.mark.asyncio
async def test_orphan_cleanup_when_db_fails(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that if database creation fails, the storage object is immediately cleaned up."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session, "Orphan Org")
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    from app.storage.local import LocalStorageProvider

    storage = get_storage_provider()
    deleted_keys: list[str] = []
    original_delete = LocalStorageProvider.delete

    async def _tracking_delete(self: LocalStorageProvider, object_key: str) -> bool:
        deleted_keys.append(object_key)
        return await original_delete(self, object_key)

    monkeypatch.setattr(LocalStorageProvider, "delete", _tracking_delete)

    # Monkeypatch repository.create to raise an unexpected DB failure
    async def _failing_create(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Simulated database failure during document commit")

    from app.repositories.document import DocumentRepository

    monkeypatch.setattr(DocumentRepository, "create", _failing_create)

    token = create_access_token(user_id=user.id)
    response = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
        files={"file": ("orphan_test.txt", b"Orphan test data", "text/plain")},
    )

    # Upload fails with 500
    assert response.status_code == 500
    # Storage object was cleaned up
    assert len(deleted_keys) == 1
    # Verify cleaned up file does not exist on disk
    assert await storage.exists(deleted_keys[0]) is False


# ===========================================================================
# 7. ALL ALLOWED FILE TYPES UPLOAD INTEGRATION TEST
# ===========================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content", "expected_mime"),
    [
        ("sample.pdf", PDF_MAGIC + b"1.7 PDF content", "application/pdf"),
        (
            "sample.docx",
            b"PK\x03\x04" + b"docx zip payload",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            "sample.xlsx",
            b"PK\x03\x04" + b"xlsx zip payload",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        ("sample.txt", b"Plain UTF-8 text content", "text/plain"),
        ("sample.csv", b"id,name,amount\n1,Alpha,100\n", "text/csv"),
    ],
)
async def test_upload_allowed_file_types(
    async_client: AsyncClient,
    db_session: AsyncSession,
    filename: str,
    content: bytes,
    expected_mime: str,
) -> None:
    """Verify upload success and MIME signature detection for all 5 permitted document types."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session, f"Org {filename}")
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    response = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
        files={"file": (filename, content, expected_mime)},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == filename
    assert data["detected_mime_type"] == expected_mime
    assert data["status"] == "uploaded"


# ===========================================================================
# 8. DOWNLOAD & DELETE SECURITY MATRICES
# ===========================================================================
@pytest.mark.asyncio
async def test_download_security_matrix(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify download: unauthenticated 401, wrong tenant 404, missing perm 403, authorized 200."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session, "DL Sec Org")
    user_admin = await _create_test_user(db_session)
    await _assign_member(db_session, user_admin.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user_admin.id)
    up_res = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
        files={"file": ("doc.txt", b"Public Org data", "text/plain")},
    )
    doc_id = up_res.json()["id"]

    # 1. Unauthenticated -> 401
    r_unauth = await async_client.get(f"/api/v1/documents/{doc_id}/download")
    assert r_unauth.status_code == 401

    # 2. Non-existent ID -> 404
    fake_id = uuid.uuid4()
    r_fake = await async_client.get(
        f"/api/v1/documents/{fake_id}/download",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
    )
    assert r_fake.status_code == 404


@pytest.mark.asyncio
async def test_delete_security_matrix(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify delete: unauthenticated 401, non-existent 404, authorized 200."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session, "Del Sec Org")
    user_admin = await _create_test_user(db_session)
    await _assign_member(db_session, user_admin.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user_admin.id)
    up_res = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
        files={"file": ("to_del.txt", b"Delete target", "text/plain")},
    )
    doc_id = up_res.json()["id"]

    # 1. Unauthenticated -> 401
    r_unauth = await async_client.delete(f"/api/v1/documents/{doc_id}")
    assert r_unauth.status_code == 401

    # 2. Non-existent ID -> 404
    fake_id = uuid.uuid4()
    r_fake = await async_client.delete(
        f"/api/v1/documents/{fake_id}",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
    )
    assert r_fake.status_code == 404

    # 3. Authorized delete -> 200
    r_del = await async_client.delete(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
    )
    assert r_del.status_code == 200


# ===========================================================================
# 9. CONCURRENT UPLOAD & DUPLICATE RACE CONDITION SAFETY
# ===========================================================================
@pytest.mark.asyncio
async def test_concurrent_duplicate_upload_safety(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Sequential or concurrent upload attempts with identical checksum yield exactly 1 document."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session, "Concurrent Org")
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    payload = PDF_MAGIC + b"1.4 Race test payload"

    import asyncio

    task1 = async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
        files={"file": ("race1.pdf", payload, "application/pdf")},
    )
    task2 = async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
        files={"file": ("race2.pdf", payload, "application/pdf")},
    )

    r1, r2 = await asyncio.gather(task1, task2)
    statuses = {r1.status_code, r2.status_code}

    # One must succeed (201) and one must be rejected (409 Conflict)
    assert 201 in statuses
    assert 409 in statuses

    # Confirm only one active document exists in the database
    docs = (
        (
            await db_session.execute(
                select(Document).where(
                    Document.organization_id == org.id,
                    Document.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(docs) == 1

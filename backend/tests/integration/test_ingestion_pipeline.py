"""Integration tests for Document Ingestion Pipeline, Status Transitions, RBAC, and Tenancy."""

import io
import uuid
from collections.abc import AsyncGenerator

import docx
import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfWriter
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
        name=name or f"Ingest Org {uid}",
        slug=f"ingest-org-{uid}",
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
        unique_email = f"ingest_user_{uid}@example.com"
    user = User(
        email=unique_email,
        password_hash=hash_password("Password123!"),
        first_name="Ingest",
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
    session: AsyncSession, user_id: uuid.UUID, organization_id: uuid.UUID, role_name: str
) -> OrganizationMember:
    role = (
        await session.execute(
            select(Role).where(
                Role.name == role_name,
                Role.organization_id.is_(None),
            )
        )
    ).scalar_one()

    membership = OrganizationMember(
        user_id=user_id,
        organization_id=organization_id,
        role_id=role.id,
    )
    session.add(membership)
    await session.flush()
    return membership


def _make_sample_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_sample_docx() -> bytes:
    doc = docx.Document()
    doc.add_heading("Financial Summary", level=1)
    doc.add_paragraph("Revenue reached 10M USD in 2026.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Region"
    table.cell(0, 1).text = "Growth"
    table.cell(1, 0).text = "EMEA"
    table.cell(1, 1).text = "15%"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_sample_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Sales"
    ws1.append(["Quarter", "Revenue"])
    ws1.append(["Q1", "500000"])
    ws2 = wb.create_sheet(title="Costs")
    ws2.append(["Category", "Amount"])
    ws2.append(["Operations", "200000"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_full_ingestion_pdf_lifecycle(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify upload -> ingest -> parsed status transition and
    canonical parsed document retrieval.
    """
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    pdf_bytes = _make_sample_pdf()
    files = {"file": ("report.pdf", pdf_bytes, "application/pdf")}

    # 1. Upload document
    resp = await async_client.post("/api/v1/documents", files=files, headers=headers)
    assert resp.status_code == 201, resp.text
    doc_data = resp.json()
    doc_id = doc_data["id"]

    # 2. Trigger synchronous ingestion
    ingest_resp = await async_client.post(
        f"/api/v1/documents/{doc_id}/ingest?sync=true",
        headers=headers,
    )
    assert ingest_resp.status_code == 200, ingest_resp.text
    parsed_meta = ingest_resp.json()
    assert parsed_meta["status"] == "parsed"
    assert parsed_meta["parser_name"] == "pypdf"
    assert parsed_meta["page_count"] == 1
    assert parsed_meta["parsed_at"] is not None

    # 3. Fetch canonical parsed representation
    get_parsed_resp = await async_client.get(
        f"/api/v1/documents/{doc_id}/parsed",
        headers=headers,
    )
    assert get_parsed_resp.status_code == 200, get_parsed_resp.text
    parsed_doc = get_parsed_resp.json()
    assert parsed_doc["document_id"] == doc_id
    assert parsed_doc["source_type"] == "pdf"
    assert len(parsed_doc["pages"]) == 1
    assert parsed_doc["parser_name"] == "pypdf"


@pytest.mark.asyncio
async def test_ingestion_csv_and_xlsx_tables(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify tabular documents (CSV, XLSX) preserve sheet and table structures."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ANALYST)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    # Upload CSV
    csv_bytes = b"Country,City,Sales\nUK,London,5000\nFR,Paris,4000"
    resp_csv = await async_client.post(
        "/api/v1/documents",
        files={"file": ("sales.csv", csv_bytes, "text/csv")},
        headers=headers,
    )
    assert resp_csv.status_code == 201
    csv_id = resp_csv.json()["id"]

    await async_client.post(f"/api/v1/documents/{csv_id}/ingest?sync=true", headers=headers)
    parsed_csv_resp = await async_client.get(f"/api/v1/documents/{csv_id}/parsed", headers=headers)
    assert parsed_csv_resp.status_code == 200
    parsed_csv = parsed_csv_resp.json()
    assert len(parsed_csv["tables"]) == 1
    assert parsed_csv["tables"][0]["headers"] == ["Country", "City", "Sales"]
    assert len(parsed_csv["tables"][0]["rows"]) == 2

    # Upload XLSX
    xlsx_bytes = _make_sample_xlsx()
    resp_xlsx = await async_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "budget.xlsx",
                xlsx_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=headers,
    )
    assert resp_xlsx.status_code == 201
    xlsx_id = resp_xlsx.json()["id"]

    await async_client.post(f"/api/v1/documents/{xlsx_id}/ingest?sync=true", headers=headers)
    parsed_xlsx_resp = await async_client.get(
        f"/api/v1/documents/{xlsx_id}/parsed",
        headers=headers,
    )
    assert parsed_xlsx_resp.status_code == 200
    parsed_xlsx = parsed_xlsx_resp.json()
    assert len(parsed_xlsx["tables"]) == 2
    sheet_names = [t["sheet_name"] for t in parsed_xlsx["tables"]]
    assert "Sales" in sheet_names
    assert "Costs" in sheet_names


@pytest.mark.asyncio
async def test_ingestion_docx_multilingual(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify DOCX parser preserves multilingual Turkish and Arabic text."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    doc = docx.Document()
    doc.add_heading("Yönetici Özeti", level=1)
    doc.add_paragraph("Türkçe karakterler: ç, ğ, ı, ö, ş, ü, İ. Şirket raporu.")
    doc.add_paragraph("Arabic: تقرير مالي فصلي متكامل")
    buf = io.BytesIO()
    doc.save(buf)

    resp = await async_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "multi.docx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        headers=headers,
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    await async_client.post(f"/api/v1/documents/{doc_id}/ingest?sync=true", headers=headers)
    parsed_resp = await async_client.get(f"/api/v1/documents/{doc_id}/parsed", headers=headers)
    assert parsed_resp.status_code == 200
    parsed = parsed_resp.json()

    all_text = " ".join(b["text"] for s in parsed["sections"] for b in s["blocks"])
    assert "Türkçe karakterler" in all_text
    assert "تقرير مالي" in all_text


@pytest.mark.asyncio
async def test_ingestion_idempotency(async_client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify that re-running ingestion multiple times converges
    deterministically without duplicate records.
    """
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    pdf_bytes = _make_sample_pdf()
    resp = await async_client.post(
        "/api/v1/documents",
        files={"file": ("repeat.pdf", pdf_bytes, "application/pdf")},
        headers=headers,
    )
    doc_id = resp.json()["id"]

    # Run ingestion 1st time
    r1 = await async_client.post(f"/api/v1/documents/{doc_id}/ingest?sync=true", headers=headers)
    assert r1.status_code == 200
    meta1 = r1.json()

    # Run ingestion 2nd time
    r2 = await async_client.post(f"/api/v1/documents/{doc_id}/ingest?sync=true", headers=headers)
    assert r2.status_code == 200
    meta2 = r2.json()

    assert meta1["status"] == meta2["status"] == "parsed"
    assert meta1["parser_name"] == meta2["parser_name"] == "pypdf"

    # Confirm only one document row exists in DB
    result = await db_session.execute(select(Document).where(Document.id == uuid.UUID(doc_id)))
    docs = result.scalars().all()
    assert len(docs) == 1


@pytest.mark.asyncio
async def test_ingestion_failure_handling(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify that corrupted documents fail gracefully with safe failure reason
    and without leaking stack traces.
    """
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
    }

    # Upload file with valid PDF magic bytes followed by corruption
    corrupt_pdf = b"%PDF-1.4\ncorrupted bytes that cannot be parsed by pypdf %%EOF"
    resp = await async_client.post(
        "/api/v1/documents",
        files={"file": ("corrupt.pdf", corrupt_pdf, "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    # Ingest should fail safely and return updated failed status
    ingest_resp = await async_client.post(
        f"/api/v1/documents/{doc_id}/ingest?sync=true",
        headers=headers,
    )
    assert ingest_resp.status_code == 200
    ingest_data = ingest_resp.json()
    assert ingest_data["status"] == "failed"
    assert ingest_data["failure_reason"] is not None

    # Inspect document detail
    detail_resp = await async_client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert detail_resp.status_code == 200
    doc = detail_resp.json()
    assert doc["status"] == "failed"
    assert doc["failure_reason"] is not None
    # Verify no stack trace or python traceback in failure reason
    assert "Traceback" not in doc["failure_reason"]
    assert "line " not in doc["failure_reason"]

    # Attempting to fetch parsed document returns 404
    parsed_resp = await async_client.get(f"/api/v1/documents/{doc_id}/parsed", headers=headers)
    assert parsed_resp.status_code == 404


@pytest.mark.asyncio
async def test_ingestion_tenant_isolation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Ensure Organization A cannot trigger ingestion or read parsed document
    belonging to Organization B.
    """
    await _ensure_rbac_seeded(db_session)
    org_a = await _create_test_organization(db_session, "Tenant A")
    org_b = await _create_test_organization(db_session, "Tenant B")

    user_a = await _create_test_user(db_session, "user_a@example.com")
    user_b = await _create_test_user(db_session, "user_b@example.com")

    await _assign_member(db_session, user_a.id, org_a.id, ROLE_ADMIN)
    await _assign_member(db_session, user_b.id, org_b.id, ROLE_ADMIN)
    await db_session.commit()

    token_a = create_access_token(user_id=user_a.id)
    token_b = create_access_token(user_id=user_b.id)

    headers_a = {"Authorization": f"Bearer {token_a}", "X-Organization-ID": str(org_a.id)}
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Organization-ID": str(org_b.id)}

    # User B uploads document under Org B
    pdf_bytes = _make_sample_pdf()
    resp_b = await async_client.post(
        "/api/v1/documents",
        files={"file": ("secret_b.pdf", pdf_bytes, "application/pdf")},
        headers=headers_b,
    )
    assert resp_b.status_code == 201
    doc_b_id = resp_b.json()["id"]

    # Ingest document B
    await async_client.post(f"/api/v1/documents/{doc_b_id}/ingest?sync=true", headers=headers_b)

    # User A tries to ingest document B -> 404
    cross_ingest = await async_client.post(
        f"/api/v1/documents/{doc_b_id}/ingest?sync=true",
        headers=headers_a,
    )
    assert cross_ingest.status_code == 404

    # User A tries to read parsed document B -> 404
    cross_read = await async_client.get(
        f"/api/v1/documents/{doc_b_id}/parsed",
        headers=headers_a,
    )
    assert cross_read.status_code == 404


@pytest.mark.asyncio
async def test_ingestion_rbac_permissions(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify RBAC: Viewer cannot ingest (403), Analyst and Admin can ingest."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session)

    admin_user = await _create_test_user(db_session, "admin@example.com")
    viewer_user = await _create_test_user(db_session, "viewer@example.com")

    await _assign_member(db_session, admin_user.id, org.id, ROLE_ADMIN)
    await _assign_member(db_session, viewer_user.id, org.id, ROLE_VIEWER)
    await db_session.commit()

    admin_token = create_access_token(user_id=admin_user.id)
    viewer_token = create_access_token(user_id=viewer_user.id)

    admin_headers = {"Authorization": f"Bearer {admin_token}", "X-Organization-ID": str(org.id)}
    viewer_headers = {"Authorization": f"Bearer {viewer_token}", "X-Organization-ID": str(org.id)}

    # Admin uploads doc
    pdf_bytes = _make_sample_pdf()
    resp = await async_client.post(
        "/api/v1/documents",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        headers=admin_headers,
    )
    doc_id = resp.json()["id"]

    # Viewer tries to trigger ingestion -> 403 Forbidden
    viewer_ingest = await async_client.post(
        f"/api/v1/documents/{doc_id}/ingest?sync=true",
        headers=viewer_headers,
    )
    assert viewer_ingest.status_code == 403

    # Admin triggers ingestion -> 200 OK
    admin_ingest = await async_client.post(
        f"/api/v1/documents/{doc_id}/ingest?sync=true",
        headers=admin_headers,
    )
    assert admin_ingest.status_code == 200

    # Viewer can read parsed representation (viewer has documents.read)
    viewer_read = await async_client.get(
        f"/api/v1/documents/{doc_id}/parsed",
        headers=viewer_headers,
    )
    assert viewer_read.status_code == 200


@pytest.mark.asyncio
async def test_delete_document_cleans_parsed_artifact(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify deleting document soft-deletes DB record and removes parsed artifact from storage."""
    await _ensure_rbac_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)
    await _assign_member(db_session, user.id, org.id, ROLE_ADMIN)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)}

    pdf_bytes = _make_sample_pdf()
    resp = await async_client.post(
        "/api/v1/documents",
        files={"file": ("to_delete.pdf", pdf_bytes, "application/pdf")},
        headers=headers,
    )
    doc_id = resp.json()["id"]

    # Ingest document
    await async_client.post(f"/api/v1/documents/{doc_id}/ingest?sync=true", headers=headers)

    storage = get_storage_provider()
    parsed_key = f"organizations/{org.id}/documents/{doc_id}/parsed.json"
    assert await storage.exists(parsed_key) is True

    # Delete document
    del_resp = await async_client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert del_resp.status_code == 200

    # Parsed artifact must be purged from storage
    assert await storage.exists(parsed_key) is False

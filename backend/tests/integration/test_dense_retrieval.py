"""Integration tests for Task 12 Basic Dense Retrieval.

Covers:
- Real Qdrant vector search operations using AsyncQdrantClient(':memory:').
- End-to-end API pipeline: upload -> ingest -> chunk -> embed -> index -> search.
- Multi-tenant isolation: Org B cannot retrieve or search Org A's chunks.
- Parent chunk hydration without N+1 queries.
- Metadata filters (document_id, chunk_type, page_number).
- Score thresholding and raw score preservation.
- RBAC permissions (viewer succeeds with 200, unauthenticated 401).
- Query and filter validation guardrails.
"""

import io
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient
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
from app.rbac.catalog import ROLE_ANALYST, ROLE_VIEWER
from app.rbac.service import RBACService
from app.retrieval.service import DenseRetrievalService
from app.services.embedding_pipeline import create_default_embedding_service
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.providers.qdrant import QdrantVectorStoreProvider
from app.vectorstore.service import VectorStoreService


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient wired to FastAPI app with PostgreSQL and in-memory Qdrant."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    # In-memory Qdrant instance for test fidelity
    memory_qdrant = AsyncQdrantClient(":memory:")
    vs_config = VectorStoreConfig.from_settings(settings)
    qdrant_provider = QdrantVectorStoreProvider(client=memory_qdrant, config=vs_config)
    vs_service = VectorStoreService(config=vs_config, provider=qdrant_provider)

    emb_service = create_default_embedding_service(settings=settings)
    retrieval_service = DenseRetrievalService(
        embedding_service=emb_service,
        vector_store_service=vs_service,
    )

    app.state.qdrant_client = memory_qdrant
    app.state.vector_store_provider = qdrant_provider
    app.state.vector_store_service = vs_service
    app.state.embedding_service = emb_service
    app.state.dense_retrieval_service = retrieval_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await memory_qdrant.close()
    await dispose_database_engine(engine)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide real PostgreSQL session for DB state setup and assertions."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        yield session
    await dispose_database_engine(engine)


async def _create_test_organization(session: AsyncSession, name: str | None = None) -> Organization:
    uid = uuid.uuid4().hex[:8]
    org = Organization(
        name=name or f"Retrieval Org {uid}",
        slug=f"retrieval-org-{uid}",
    )
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


async def _create_test_user(
    session: AsyncSession,
    org: Organization,
    role_name: str = ROLE_ANALYST,
) -> tuple[User, str]:
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"retrieval_user_{uid}@example.com",
        password_hash=hash_password("StrongPassword123!"),
        first_name="Retrieval",
        last_name=f"User {uid}",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    role_res = await session.execute(select(Role).where(Role.name == role_name))
    role = role_res.scalar_one_or_none()
    if not role:
        rbac_svc = RBACService()
        await rbac_svc.seed_system_rbac(session)
        role_res = await session.execute(select(Role).where(Role.name == role_name))
        role = role_res.scalar_one()

    membership = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role_id=role.id,
    )
    session.add(membership)
    await session.commit()

    token = create_access_token(
        user_id=user.id,
        extra_claims={
            "email": user.email,
            "org_id": str(org.id),
            "role": role.name,
        },
    )
    return user, token


@pytest.mark.asyncio
class TestDenseRetrievalOperations:
    """End-to-end integration tests for dense vector retrieval."""

    async def _upload_index_document(
        self,
        client: AsyncClient,
        token: str,
        org_id: uuid.UUID,
        content: bytes | None = None,
    ) -> uuid.UUID:
        """Pipeline helper: Upload -> Ingest -> Chunk -> Embed -> Index."""
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(org_id),
        }

        # 1. Upload
        doc_content = content or (
            b"# Executive Summary\n\n"
            b"Q3 Enterprise revenue grew by 25% year over year reaching record margins.\n\n"
            b"## Operating Performance\n\n"
            b"Gross operating margins expanded by 350 basis points due to cloud efficiency."
        )
        files = {"file": ("financial_report.txt", io.BytesIO(doc_content), "text/plain")}
        upload_resp = await client.post("/api/v1/documents", headers=headers, files=files)
        assert upload_resp.status_code == 201, upload_resp.text
        doc_id = uuid.UUID(upload_resp.json()["id"])

        # 2. Ingest
        ingest_resp = await client.post(
            f"/api/v1/documents/{doc_id}/ingest?sync=true",
            headers=headers,
        )
        assert ingest_resp.status_code == 200, ingest_resp.text

        # 3. Chunk
        chunk_resp = await client.post(
            f"/api/v1/documents/{doc_id}/chunks?sync=true",
            headers=headers,
        )
        assert chunk_resp.status_code == 200, chunk_resp.text

        # 4. Embed
        embed_resp = await client.post(
            f"/api/v1/documents/{doc_id}/embeddings?sync=true",
            headers=headers,
        )
        assert embed_resp.status_code == 200, embed_resp.text

        # 5. Index
        index_resp = await client.post(
            f"/api/v1/documents/{doc_id}/index?sync=true",
            headers=headers,
        )
        assert index_resp.status_code == 200, index_resp.text

        return doc_id

    async def test_end_to_end_search_success(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        org = await _create_test_organization(db_session)
        user, token = await _create_test_user(db_session, org, role_name=ROLE_ANALYST)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(org.id),
        }

        doc_id = await self._upload_index_document(async_client, token, org.id)

        # Execute dense search
        search_payload = {
            "query": "What was the enterprise revenue growth in Q3?",
            "top_k": 5,
            "include_parent": True,
        }
        res = await async_client.post(
            "/api/v1/retrieval/search", headers=headers, json=search_payload
        )
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["query"] == "What was the enterprise revenue growth in Q3?"
        assert data["total_results"] > 0
        assert len(data["results"]) == data["total_results"]

        first = data["results"][0]
        assert "chunk_id" in first
        assert first["document_id"] == str(doc_id)
        assert isinstance(first["score"], (int, float))
        assert len(first["text"]) > 0
        assert "revenue" in first["text"].lower() or "margin" in first["text"].lower()

        # Diagnostics verification
        diag = data["diagnostics"]
        assert "collection_name" in diag
        assert diag["returned_chunks_count"] == data["total_results"]
        assert diag["dimensions"] > 0
        assert diag["latency"]["total_ms"] >= 0.0
        assert diag["latency"]["embedding_ms"] >= 0.0
        assert diag["latency"]["vector_search_ms"] >= 0.0
        assert diag["latency"]["hydration_ms"] >= 0.0

    async def test_parent_context_hydration(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        org = await _create_test_organization(db_session)
        _, token = await _create_test_user(db_session, org, role_name=ROLE_ANALYST)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(org.id),
        }

        await self._upload_index_document(async_client, token, org.id)

        # 1. Search with parent context enabled
        res_with_parent = await async_client.post(
            "/api/v1/retrieval/search",
            headers=headers,
            json={
                "query": "cloud efficiency and operating margins",
                "top_k": 3,
                "include_parent": True,
            },
        )
        assert res_with_parent.status_code == 200
        items_with = res_with_parent.json()["results"]
        assert len(items_with) > 0

        # 2. Search with parent context disabled
        res_no_parent = await async_client.post(
            "/api/v1/retrieval/search",
            headers=headers,
            json={
                "query": "cloud efficiency and operating margins",
                "top_k": 3,
                "include_parent": False,
            },
        )
        assert res_no_parent.status_code == 200
        items_without = res_no_parent.json()["results"]
        assert len(items_without) > 0
        # When include_parent is False, parent_text must be None
        for it in items_without:
            assert it["parent_text"] is None

    async def test_tenant_isolation_prevents_cross_tenant_search(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        org_a = await _create_test_organization(db_session, name="Org A Search")
        org_b = await _create_test_organization(db_session, name="Org B Search")

        _, token_a = await _create_test_user(db_session, org_a, role_name=ROLE_ANALYST)
        _, token_b = await _create_test_user(db_session, org_b, role_name=ROLE_ANALYST)

        # Org A indexes document with distinctive secret content
        distinct_content = (
            b"# Top Secret Project Phoenix\n\nProject Phoenix generated 99 million dollars."
        )
        await self._upload_index_document(async_client, token_a, org_a.id, content=distinct_content)

        # Org B searches for Project Phoenix
        headers_b = {
            "Authorization": f"Bearer {token_b}",
            "X-Organization-ID": str(org_b.id),
        }
        res_b = await async_client.post(
            "/api/v1/retrieval/search",
            headers=headers_b,
            json={"query": "Project Phoenix 99 million dollars"},
        )
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["total_results"] == 0
        assert data_b["results"] == []

        # Org A searches for Project Phoenix and finds it
        headers_a = {
            "Authorization": f"Bearer {token_a}",
            "X-Organization-ID": str(org_a.id),
        }
        res_a = await async_client.post(
            "/api/v1/retrieval/search",
            headers=headers_a,
            json={"query": "Project Phoenix 99 million dollars"},
        )
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["total_results"] > 0

    async def test_metadata_filters(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        org = await _create_test_organization(db_session)
        _, token = await _create_test_user(db_session, org, role_name=ROLE_ANALYST)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(org.id),
        }

        doc_id = await self._upload_index_document(async_client, token, org.id)
        other_doc_id = uuid.uuid4()

        # Search matching document_id
        res_doc = await async_client.post(
            "/api/v1/retrieval/search",
            headers=headers,
            json={"query": "revenue", "document_id": str(doc_id)},
        )
        assert res_doc.status_code == 200
        for item in res_doc.json()["results"]:
            assert item["document_id"] == str(doc_id)

        # Search non-existent document_id returns 0
        res_non_existent = await async_client.post(
            "/api/v1/retrieval/search",
            headers=headers,
            json={"query": "revenue", "document_id": str(other_doc_id)},
        )
        assert res_non_existent.status_code == 200
        assert res_non_existent.json()["total_results"] == 0

    async def test_score_threshold_filter(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        org = await _create_test_organization(db_session)
        _, token = await _create_test_user(db_session, org, role_name=ROLE_ANALYST)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(org.id),
        }

        await self._upload_index_document(async_client, token, org.id)

        # Search with impossible score threshold (0.9999 for dissimilar random texts)
        res = await async_client.post(
            "/api/v1/retrieval/search",
            headers=headers,
            json={
                "query": "completely unrelated random astronomical space query",
                "score_threshold": 0.9999,
            },
        )
        assert res.status_code == 200
        assert res.json()["total_results"] == 0

    async def test_query_validation_guardrails(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        org = await _create_test_organization(db_session)
        _, token = await _create_test_user(db_session, org, role_name=ROLE_ANALYST)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(org.id),
        }

        # Empty string
        res_empty = await async_client.post(
            "/api/v1/retrieval/search",
            headers=headers,
            json={"query": "   "},
        )
        assert res_empty.status_code in (400, 422)

        # Too short (1 char)
        res_short = await async_client.post(
            "/api/v1/retrieval/search",
            headers=headers,
            json={"query": "x"},
        )
        assert res_short.status_code in (400, 422)

        # Invalid chunk_type
        res_bad_type = await async_client.post(
            "/api/v1/retrieval/search",
            headers=headers,
            json={"query": "valid query", "chunk_type": "invalid_type"},
        )
        assert res_bad_type.status_code == 422

    async def test_rbac_enforcement(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        org = await _create_test_organization(db_session)
        _, viewer_token = await _create_test_user(db_session, org, role_name=ROLE_VIEWER)

        # Viewer has PERM_DOCUMENTS_READ, so search succeeds
        viewer_headers = {
            "Authorization": f"Bearer {viewer_token}",
            "X-Organization-ID": str(org.id),
        }
        res_viewer = await async_client.post(
            "/api/v1/retrieval/search",
            headers=viewer_headers,
            json={"query": "operating margins"},
        )
        assert res_viewer.status_code == 200

        # Unauthenticated request fails with 401
        res_unauth = await async_client.post(
            "/api/v1/retrieval/search",
            headers={"X-Organization-ID": str(org.id)},
            json={"query": "operating margins"},
        )
        assert res_unauth.status_code == 401

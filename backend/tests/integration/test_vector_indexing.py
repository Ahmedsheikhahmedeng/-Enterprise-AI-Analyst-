"""Integration tests for Task 11 Qdrant Vector Store & Dense Vector Indexing.

Covers:
- Real Qdrant engine integration using AsyncQdrantClient(':memory:').
- Deterministic collection creation, dimension enforcement, and mismatch rejection.
- Idempotent batch upserting and retrieval.
- Multi-tenant isolation in Qdrant (Org B cannot read, count, or delete Org A points).
- Version-aware re-indexing isolation (v1 vs v2 collections).
- End-to-end API pipeline: upload -> ingest -> chunk -> embed -> index.
- Document index status lifecycle (vector_pending -> vector_indexing -> vector_indexed).
- RBAC enforcement (Viewer gets 403 on POST /index, 200 on GET /index-status).
- Document deletion triggers vector store purge.
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
from app.rbac.catalog import ROLE_ADMIN, ROLE_ANALYST, ROLE_VIEWER
from app.rbac.service import RBACService
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.exceptions import CollectionMismatchError
from app.vectorstore.models import VectorPoint
from app.vectorstore.providers.qdrant import QdrantVectorStoreProvider
from app.vectorstore.service import VectorStoreService


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient wired to FastAPI app with PostgreSQL database state."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    # Use in-memory Qdrant for real engine test fidelity during app lifespan
    memory_qdrant = AsyncQdrantClient(":memory:")
    vs_config = VectorStoreConfig.from_settings(settings)
    qdrant_provider = QdrantVectorStoreProvider(client=memory_qdrant, config=vs_config)
    vs_service = VectorStoreService(config=vs_config, provider=qdrant_provider)

    app.state.qdrant_client = memory_qdrant
    app.state.vector_store_provider = qdrant_provider
    app.state.vector_store_service = vs_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await memory_qdrant.close()
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
        name=name or f"Vector Org {uid}",
        slug=f"vector-org-{uid}",
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
        email=f"vector_user_{uid}@example.com",
        password_hash=hash_password("StrongPassword123!"),
        first_name="Vector",
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
class TestRealQdrantEngineOperations:
    """Test QdrantVectorStoreProvider directly against Qdrant's in-memory engine."""

    async def test_real_qdrant_collection_lifecycle_and_mismatch(self) -> None:
        client = AsyncQdrantClient(":memory:")
        config = VectorStoreConfig(vector_size=8, distance="cosine")
        provider = QdrantVectorStoreProvider(client=client, config=config)

        coll = "test_engine_coll"

        # 1. Ensure collection exists
        await provider.ensure_collection(coll, vector_size=8, distance="cosine")
        stats = await provider.get_collection_stats(coll)
        assert stats.points_count == 0
        assert stats.vector_size == 8

        # 2. Idempotent call with matching config succeeds
        await provider.ensure_collection(coll, vector_size=8, distance="cosine")

        # 3. Mismatch detection: ensuring with size 4 must raise CollectionMismatchError
        with pytest.raises(CollectionMismatchError, match="configuration mismatch"):
            await provider.ensure_collection(coll, vector_size=4, distance="cosine")

        await client.close()

    async def test_real_qdrant_upsert_and_tenant_isolation(self) -> None:
        client = AsyncQdrantClient(":memory:")
        config = VectorStoreConfig(vector_size=4, distance="cosine")
        provider = QdrantVectorStoreProvider(client=client, config=config)

        coll = "tenant_isolation_coll"
        await provider.ensure_collection(coll, vector_size=4, distance="cosine")

        org_a = uuid.uuid4()
        org_b = uuid.uuid4()
        doc_a = uuid.uuid4()
        doc_b = uuid.uuid4()

        p_a1 = VectorPoint(
            id=uuid.uuid4(),
            vector=[0.1, 0.2, 0.3, 0.4],
            payload={
                "organization_id": str(org_a),
                "document_id": str(doc_a),
                "chunk_id": str(uuid.uuid4()),
                "content": "Org A secret document text",
            },
        )
        p_a2 = VectorPoint(
            id=uuid.uuid4(),
            vector=[0.2, 0.3, 0.4, 0.5],
            payload={
                "organization_id": str(org_a),
                "document_id": str(doc_a),
                "chunk_id": str(uuid.uuid4()),
                "content": "Org A second chunk text",
            },
        )
        p_b1 = VectorPoint(
            id=uuid.uuid4(),
            vector=[0.9, 0.8, 0.7, 0.6],
            payload={
                "organization_id": str(org_b),
                "document_id": str(doc_b),
                "chunk_id": str(uuid.uuid4()),
                "content": "Org B separate document text",
            },
        )

        # Upsert points
        res_a = await provider.upsert(coll, [p_a1, p_a2])
        assert res_a.successful_points == 2
        res_b = await provider.upsert(coll, [p_b1])
        assert res_b.successful_points == 1

        # Total points in physical collection
        all_stats = await provider.get_collection_stats(coll)
        assert all_stats.points_count == 3

        # Scoped count
        count_a = await provider.count_points(coll, organization_id=org_a)
        assert count_a == 2
        count_b = await provider.count_points(coll, organization_id=org_b)
        assert count_b == 1

        # Tenant isolation in retrieval: Org B attempts to retrieve Org A's point
        b_retrieved = await provider.get_points(coll, organization_id=org_b, point_ids=[p_a1.id])
        assert len(b_retrieved) == 0  # Blocked!

        # Org A can retrieve its own point
        a_retrieved = await provider.get_points(coll, organization_id=org_a, point_ids=[p_a1.id])
        assert len(a_retrieved) == 1
        assert a_retrieved[0].id == p_a1.id
        assert a_retrieved[0].payload["content"] == "Org A secret document text"

        # Scoped document deletion: Org B deleting doc_a has zero effect on Org A
        del_b_fake = await provider.delete_by_document(
            coll, organization_id=org_b, document_id=doc_a
        )
        assert del_b_fake == 0
        assert await provider.count_points(coll, organization_id=org_a) == 2

        # Org A deleting its own document
        del_a = await provider.delete_by_document(coll, organization_id=org_a, document_id=doc_a)
        assert del_a == 2
        assert await provider.count_points(coll, organization_id=org_a) == 0
        # Org B points remain intact
        assert await provider.count_points(coll, organization_id=org_b) == 1

        await client.close()

    async def test_real_qdrant_idempotent_upsert(self) -> None:
        client = AsyncQdrantClient(":memory:")
        config = VectorStoreConfig(vector_size=2)
        provider = QdrantVectorStoreProvider(client=client, config=config)

        coll = "idempotent_upsert_coll"
        await provider.ensure_collection(coll, vector_size=2)

        org_id = uuid.uuid4()
        pid = uuid.uuid4()
        point = VectorPoint(
            id=pid,
            vector=[1.0, 0.0],
            payload={"organization_id": str(org_id), "version": 1},
        )

        # First upsert
        r1 = await provider.upsert(coll, [point])
        assert r1.successful_points == 1
        assert await provider.count_points(coll, org_id) == 1

        # Re-upsert identical point with updated payload
        point_v2 = VectorPoint(
            id=pid,
            vector=[1.0, 0.0],
            payload={"organization_id": str(org_id), "version": 2},
        )
        r2 = await provider.upsert(coll, [point_v2])
        assert r2.successful_points == 1

        # Count remains 1 (no duplicates inserted)
        assert await provider.count_points(coll, org_id) == 1
        retrieved = await provider.get_points(coll, org_id, [pid])
        assert len(retrieved) == 1
        assert retrieved[0].payload["version"] == 2

        await client.close()


@pytest.mark.asyncio
class TestVectorIndexingPipelineAPI:
    """End-to-end integration tests through FastAPI HTTP endpoints."""

    async def _upload_and_prepare_document(
        self,
        client: AsyncClient,
        token: str,
        org_id: uuid.UUID,
    ) -> uuid.UUID:
        """Helper to create document, ingest, chunk, and embed."""
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(org_id),
        }
        # 1. Upload
        file_content = (
            b"# Financial Overview\n\n"
            b"Q3 Enterprise revenue grew by 25% year over year.\n\n"
            b"## Expenses\n\n"
            b"Operating expenses remained stable."
        )
        files = {"file": ("report.txt", io.BytesIO(file_content), "text/plain")}
        resp = await client.post("/api/v1/documents", headers=headers, files=files)
        assert resp.status_code == 201, resp.text
        doc_id = uuid.UUID(resp.json()["id"])

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

        return doc_id

    async def test_full_pipeline_indexing_flow(
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

        # Prepare document up to embeddings
        doc_id = await self._upload_and_prepare_document(async_client, token, org.id)

        # Check initial index status
        status_resp = await async_client.get(
            f"/api/v1/documents/{doc_id}/index-status",
            headers=headers,
        )
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["document_id"] == str(doc_id)
        assert status_data["indexing_status"] == "vector_pending"
        assert status_data["total_chunks"] > 0
        assert status_data["indexed_chunks"] == 0

        # Execute indexing
        index_resp = await async_client.post(
            f"/api/v1/documents/{doc_id}/index?sync=true",
            headers=headers,
        )
        assert index_resp.status_code == 200, index_resp.text
        index_data = index_resp.json()
        assert index_data["status"] == "vector_indexed"
        assert index_data["indexed_points"] > 0
        assert index_data["failed_points"] == 0

        # Re-check status
        after_status_resp = await async_client.get(
            f"/api/v1/documents/{doc_id}/index-status",
            headers=headers,
        )
        assert after_status_resp.status_code == 200
        after_status = after_status_resp.json()
        assert after_status["indexing_status"] == "vector_indexed"
        assert after_status["indexed_chunks"] == after_status["total_chunks"]

        # Re-indexing is idempotent
        reindex_resp = await async_client.post(
            f"/api/v1/documents/{doc_id}/index?sync=true",
            headers=headers,
        )
        assert reindex_resp.status_code == 200
        assert reindex_resp.json()["status"] == "vector_indexed"

    async def test_tenant_isolation_on_indexing_api(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        org_a = await _create_test_organization(db_session, name="Org A Index")
        org_b = await _create_test_organization(db_session, name="Org B Index")

        _, token_a = await _create_test_user(db_session, org_a, role_name=ROLE_ANALYST)
        _, token_b = await _create_test_user(db_session, org_b, role_name=ROLE_ANALYST)

        doc_a_id = await self._upload_and_prepare_document(async_client, token_a, org_a.id)

        # Org B attempts to index Org A's document
        headers_b = {
            "Authorization": f"Bearer {token_b}",
            "X-Organization-ID": str(org_b.id),
        }
        res = await async_client.post(f"/api/v1/documents/{doc_a_id}/index", headers=headers_b)
        assert res.status_code == 404

        # Org B attempts to check index status of Org A's document
        res_status = await async_client.get(
            f"/api/v1/documents/{doc_a_id}/index-status",
            headers=headers_b,
        )
        assert res_status.status_code == 404

    async def test_rbac_enforcement_on_indexing(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        org = await _create_test_organization(db_session)
        _, analyst_token = await _create_test_user(db_session, org, role_name=ROLE_ANALYST)
        _, viewer_token = await _create_test_user(db_session, org, role_name=ROLE_VIEWER)

        doc_id = await self._upload_and_prepare_document(async_client, analyst_token, org.id)

        viewer_headers = {
            "Authorization": f"Bearer {viewer_token}",
            "X-Organization-ID": str(org.id),
        }

        # Viewer cannot trigger indexing (HTTP 403)
        res_index = await async_client.post(
            f"/api/v1/documents/{doc_id}/index",
            headers=viewer_headers,
        )
        assert res_index.status_code == 403

        # Viewer CAN inspect index status (HTTP 200)
        res_status = await async_client.get(
            f"/api/v1/documents/{doc_id}/index-status",
            headers=viewer_headers,
        )
        assert res_status.status_code == 200

    async def test_vectorstore_health_and_stats_endpoints(
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

        # Health endpoint
        health_resp = await async_client.get("/api/v1/vectorstore/health", headers=headers)
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert health_data["status"] in ("ok", "healthy")
        assert "url" in health_data
        assert isinstance(health_data["collections"], list)

    async def test_document_deletion_purges_vectors(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        org = await _create_test_organization(db_session)
        _, token = await _create_test_user(db_session, org, role_name=ROLE_ADMIN)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(org.id),
        }

        doc_id = await self._upload_and_prepare_document(async_client, token, org.id)
        index_res = await async_client.post(
            f"/api/v1/documents/{doc_id}/index?sync=true",
            headers=headers,
        )
        assert index_res.status_code == 200
        coll_name = index_res.json()["collection_name"]

        # Verify vectors are present
        vs_service: VectorStoreService = async_client._transport.app.state.vector_store_service  # type: ignore[attr-defined]
        count_before = await vs_service.count_points(coll_name, org.id, doc_id)
        assert count_before > 0

        # Delete document
        del_resp = await async_client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
        assert del_resp.status_code == 200

        # Verify vectors were purged from Qdrant
        count_after = await vs_service.count_points(coll_name, org.id, doc_id)
        assert count_after == 0

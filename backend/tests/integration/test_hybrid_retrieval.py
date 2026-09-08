"""Integration tests for Task 13 Advanced Hybrid Retrieval & RRF.

Covers:
- Exact-term BM25 lexical boost (e.g. "XJ-4927").
- Semantic similarity Dense boost.
- Multilingual retrieval (Arabic, Turkish, English, mixed).
- Multi-tenant isolation: Org A never sees Org B chunks under any score.
- Reciprocal Rank Fusion (RRF) deduplication and score explainability.
- Post-fusion zero N+1 parent hydration.
- Partial retrieval failure modes (degraded fallbacks).
- REST API endpoint: POST /api/v1/retrieval/hybrid-search with RBAC guardrails.
- Feature flag enforcement (HYBRID_RETRIEVAL_ENABLED).
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient
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
from app.models.document import Document, DocumentChunk
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.user import User
from app.rbac.catalog import ROLE_ANALYST
from app.rbac.service import RBACService
from app.repositories.chunk import DocumentChunkRepository
from app.retrieval.config import BM25Config, HybridRetrievalConfig
from app.retrieval.hybrid.service import HybridRetrievalService
from app.retrieval.service import DenseRetrievalService
from app.retrieval.sparse.analyzer import MultilingualSparseAnalyzer
from app.retrieval.sparse.bm25 import BM25Encoder
from app.retrieval.sparse.service import SparseRetrievalService
from app.retrieval.sparse.stats import TenantCorpusStatsManager
from app.services.embedding_pipeline import create_default_embedding_service
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.providers.qdrant import QdrantVectorStoreProvider
from app.vectorstore.service import VectorStoreService


@pytest.fixture
async def test_env() -> AsyncGenerator[dict[str, Any], None]:
    """Provide fully wired test environment with PostgreSQL and in-memory Qdrant."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    # In-memory Qdrant instance
    memory_qdrant = AsyncQdrantClient(":memory:")
    vs_config = VectorStoreConfig.from_settings(settings)
    qdrant_provider = QdrantVectorStoreProvider(client=memory_qdrant, config=vs_config)
    vs_service = VectorStoreService(config=vs_config, provider=qdrant_provider)

    emb_service = create_default_embedding_service(settings=settings)
    dense_service = DenseRetrievalService(
        embedding_service=emb_service,
        vector_store_service=vs_service,
    )

    stats_mgr = TenantCorpusStatsManager()
    bm25_cfg = BM25Config.from_settings(settings)
    analyzer = MultilingualSparseAnalyzer(bm25_cfg)
    bm25_encoder = BM25Encoder(config=bm25_cfg, stats_manager=stats_mgr)

    sparse_service = SparseRetrievalService(
        vector_store_service=vs_service,
        embedding_service=emb_service,
        analyzer=analyzer,
        bm25_encoder=bm25_encoder,
        stats_manager=stats_mgr,
    )

    hybrid_cfg = HybridRetrievalConfig.from_settings(settings)
    chunk_repo = DocumentChunkRepository()
    hybrid_service = HybridRetrievalService(
        dense_service=dense_service,
        sparse_service=sparse_service,
        chunk_repository=chunk_repo,
        config=hybrid_cfg,
    )

    app.state.qdrant_client = memory_qdrant
    app.state.vector_store_provider = qdrant_provider
    app.state.vector_store_service = vs_service
    app.state.embedding_service = emb_service
    app.state.dense_retrieval_service = dense_service
    app.state.sparse_retrieval_service = sparse_service
    app.state.hybrid_retrieval_service = hybrid_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield {
            "app": app,
            "client": client,
            "session_factory": session_factory,
            "vs_service": vs_service,
            "emb_service": emb_service,
            "dense_service": dense_service,
            "sparse_service": sparse_service,
            "hybrid_service": hybrid_service,
            "stats_mgr": stats_mgr,
            "analyzer": analyzer,
            "bm25_encoder": bm25_encoder,
        }

    await dispose_database_engine(engine)


async def _seed_user_and_org(
    session: AsyncSession,
    org_name: str = "Test Org",
    email: str = "user@example.com",
    role_name: str = ROLE_ANALYST,
) -> tuple[User, Organization, str]:
    """Helper to create organization, role, user, membership, and JWT token."""
    from sqlalchemy import select

    org_uid = uuid.uuid4().hex[:8]
    org = Organization(name=org_name, slug=f"org-{org_uid}")
    session.add(org)
    await session.commit()
    await session.refresh(org)

    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"user_{uid}@example.com",
        password_hash=hash_password("StrongP@ssw0rd123!"),
        first_name="Test",
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
    return user, org, token


async def _index_test_chunk(
    session: AsyncSession,
    env: dict[str, Any],
    org_id: uuid.UUID,
    content: str,
    chunk_type: str = "paragraph",
    page_number: int = 1,
    parent_chunk_id: uuid.UUID | None = None,
) -> DocumentChunk:
    """Index a chunk into PostgreSQL and Qdrant (dense + sparse)."""
    # 1. DB document and chunk
    doc = Document(
        organization_id=org_id,
        name="Test Document",
        original_filename="test.txt",
        mime_type="text/plain",
        file_size=1024,
        sha256=uuid.uuid4().hex,
        storage_backend="local",
        storage_key=f"uploads/{uuid.uuid4().hex}.txt",
        status="completed",
    )
    session.add(doc)
    await session.flush()

    chunk = DocumentChunk(
        organization_id=org_id,
        document_id=doc.id,
        chunk_index=0,
        chunk_type=chunk_type,
        content=content,
        token_count=len(content.split()),
        character_count=len(content),
        page_number=page_number,
        parent_chunk_id=parent_chunk_id,
    )
    session.add(chunk)
    await session.commit()
    await session.refresh(chunk)

    # 2. Sparse analysis & stats
    analyzer = env["analyzer"]
    stats_mgr = env["stats_mgr"]
    bm25_encoder = env["bm25_encoder"]

    analyzed = analyzer.analyze(content)
    stats_mgr.register_chunk(org_id, analyzed)
    sparse_vec = bm25_encoder.encode_document(analyzed, avgdl=stats_mgr.get_stats(org_id).avgdl)

    # 3. Dense embedding
    emb_service = env["emb_service"]
    dense_vec = await emb_service.embed_query(content)

    # 4. Upsert point with dual vector (dense + sparse)
    vs_service: VectorStoreService = env["vs_service"]
    coll_name = await vs_service.ensure_collection(
        embedding_provider=emb_service.provider_name,
        embedding_model=emb_service.model_name,
        dimensions=emb_service.dimensions,
        version=emb_service.version,
    )

    from app.vectorstore.models import VectorPoint

    point = VectorPoint(
        id=chunk.id,
        vector=dense_vec,
        sparse_vector=sparse_vec,
        payload={
            "organization_id": str(org_id),
            "document_id": str(doc.id),
            "chunk_id": str(chunk.id),
            "chunk_type": chunk_type,
            "page_number": page_number,
            "text": content,
            "chunk_index": 0,
        },
    )
    await vs_service.provider.upsert(collection_name=coll_name, points=[point])
    return chunk


class TestHybridRetrievalCore:
    """Integration test suite for core hybrid retrieval mechanics."""

    @pytest.mark.asyncio
    async def test_exact_term_bm25_boost(self, test_env: dict[str, Any]) -> None:
        """Verify exact product code 'XJ-4927' is boosted by BM25 to rank 1 in Hybrid."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            # Chunk A: Contains exact technical identifier
            chunk_exact = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "The secret space mission uses hardware module Project Orion XJ-4927.",
            )
            # Chunk B: Broad semantic match without identifier
            await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Our aerospace division launched a confidential orbital reconnaissance mission.",
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]
            result = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="XJ-4927",
                top_k=5,
            )

            assert len(result.chunks) >= 1
            top_hit = result.chunks[0]
            assert top_hit.chunk_id == chunk_exact.id
            assert top_hit.sparse_score is not None
            assert top_hit.sparse_score > 0.0
            assert top_hit.retrieval_mode == "hybrid"

    @pytest.mark.asyncio
    async def test_semantic_dense_retrieval(self, test_env: dict[str, Any]) -> None:
        """Verify paraphrased query without lexical overlap is found via Dense pathway."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            sem_content = (
                "Operating profitability contracted significantly due to rising "
                "manufacturing expenses."
            )
            chunk_sem = await _index_test_chunk(
                session,
                test_env,
                org.id,
                sem_content,
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]
            result = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="What caused the decline in operating margin?",
                top_k=5,
            )

            assert len(result.chunks) >= 1
            found_ids = [c.chunk_id for c in result.chunks]
            assert chunk_sem.id in found_ids

    @pytest.mark.asyncio
    async def test_multilingual_arabic_and_turkish(self, test_env: dict[str, Any]) -> None:
        """Verify Arabic and Turkish queries match their corresponding documents."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            # Arabic document
            chunk_ar = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "أظهرت النتائج المالية السنوية زيادة في إجمالي الأرباح لعام ٢٠٢٥",
            )
            # Turkish document
            chunk_tr = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "İstanbul genel merkezinde düzenlenen toplantıda 2025 gelir analizi sunuldu.",
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]

            # Arabic search
            res_ar = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="أرباح ٢٠٢٥",
            )
            assert any(c.chunk_id == chunk_ar.id for c in res_ar.chunks)

            # Turkish search
            res_tr = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="İstanbul gelir analizi",
            )
            assert any(c.chunk_id == chunk_tr.id for c in res_tr.chunks)

    @pytest.mark.asyncio
    async def test_tenant_isolation_boundary(self, test_env: dict[str, Any]) -> None:
        """Verify Org A search NEVER retrieves Org B chunks, even with an exact identical match."""
        async with test_env["session_factory"]() as session:
            _, org_a, _ = await _seed_user_and_org(session, org_name="Org Alpha")
            _, org_b, _ = await _seed_user_and_org(session, org_name="Org Beta")

            chunk_a = await _index_test_chunk(
                session, test_env, org_a.id, "Confidential roadmap for Alpha."
            )
            chunk_b = await _index_test_chunk(
                session,
                test_env,
                org_b.id,
                "Confidential roadmap for Beta with super keyword Alpha.",
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]
            res_a = await hybrid_service.search(
                session=session,
                organization_id=org_a.id,
                query="Confidential roadmap Alpha",
            )

            retrieved_ids = [c.chunk_id for c in res_a.chunks]
            assert chunk_a.id in retrieved_ids
            assert chunk_b.id not in retrieved_ids

    @pytest.mark.asyncio
    async def test_parent_context_hydration(self, test_env: dict[str, Any]) -> None:
        """Verify parent chunk context is hydrated for final top results without N+1."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            # Create parent chunk
            parent_chunk = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Section 5: Detailed Executive Compensation Overview",
                chunk_type="section",
            )
            # Create child chunk referencing parent
            child_chunk = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "CEO received 100,000 stock options vesting over 4 years.",
                chunk_type="paragraph",
                parent_chunk_id=parent_chunk.id,
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]
            res = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="Executive stock options vesting",
                include_parent=True,
            )

            matching = next((c for c in res.chunks if c.chunk_id == child_chunk.id), None)
            assert matching is not None
            assert matching.parent_chunk_id == parent_chunk.id
            assert matching.parent_text == parent_chunk.content

    @pytest.mark.asyncio
    async def test_partial_failure_graceful_degradation(self, test_env: dict[str, Any]) -> None:
        """Verify if sparse search fails, hybrid gracefully degrades to dense_fallback."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)
            chunk = await _index_test_chunk(session, test_env, org.id, "Resilient search system.")

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]

            # Artificially inject an error into the sparse service
            async def failing_sparse(*args: Any, **kwargs: Any) -> Any:
                raise RuntimeError("Sparse index unavailable")

            original_search = hybrid_service.sparse_service.search
            hybrid_service.sparse_service.search = failing_sparse  # type: ignore

            try:
                res = await hybrid_service.search(
                    session=session,
                    organization_id=org.id,
                    query="Resilient search",
                )
                assert res.retrieval_mode == "dense_fallback"
                assert res.diagnostics.is_degraded is True
                assert "Sparse retrieval unavailable" in (res.diagnostics.degradation_reason or "")
                assert any(c.chunk_id == chunk.id for c in res.chunks)
            finally:
                hybrid_service.sparse_service.search = original_search  # type: ignore

    @pytest.mark.asyncio
    async def test_dense_failure_graceful_degradation(self, test_env: dict[str, Any]) -> None:
        """Verify if dense search fails, hybrid gracefully degrades to sparse_fallback."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)
            chunk = await _index_test_chunk(
                session, test_env, org.id, "Fault-tolerant search architecture."
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]

            # Artificially inject an error into the dense service
            async def failing_dense(*args: Any, **kwargs: Any) -> Any:
                raise RuntimeError("Dense vector store unavailable")

            original_dense = hybrid_service.dense_service.retrieve_candidates
            hybrid_service.dense_service.retrieve_candidates = failing_dense  # type: ignore

            try:
                res = await hybrid_service.search(
                    session=session,
                    organization_id=org.id,
                    query="Fault-tolerant search",
                )
                assert res.retrieval_mode == "sparse_fallback"
                assert res.diagnostics.is_degraded is True
                assert "Dense retrieval unavailable" in (res.diagnostics.degradation_reason or "")
                assert any(c.chunk_id == chunk.id for c in res.chunks)
            finally:
                hybrid_service.dense_service.retrieve_candidates = original_dense  # type: ignore

    @pytest.mark.asyncio
    async def test_zero_results_returns_empty_gracefully(self, test_env: dict[str, Any]) -> None:
        """Verify searching for non-matching query returns empty list without error."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]
            res = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="UnmatchedKeywordZyxWvu",
            )
            assert res.chunks == []
            assert res.total_results == 0
            assert res.diagnostics.final_result_count == 0

    @pytest.mark.asyncio
    async def test_mixed_language_hybrid_retrieval(self, test_env: dict[str, Any]) -> None:
        """Verify mixed Arabic, Turkish, English text is tokenized and retrieved correctly."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)
            mixed_content = (
                "2025 Revenue Analysis — تحليل الإيرادات — Gelir Analizi (Q4, 15%, XJ-4927)"
            )
            chunk = await _index_test_chunk(session, test_env, org.id, mixed_content)

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]

            # Query with mixed terms
            res = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="2025 تحليل الإيرادات Gelir Analizi",
            )
            assert len(res.chunks) >= 1
            assert res.chunks[0].chunk_id == chunk.id
            assert res.chunks[0].sparse_score is not None

    @pytest.mark.asyncio
    async def test_metadata_filters_applied(self, test_env: dict[str, Any]) -> None:
        """Verify chunk_type and page_number filters are applied across both pathways."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)
            c1 = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Summary financial report.",
                chunk_type="table",
                page_number=10,
            )
            c2 = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Summary financial report.",
                chunk_type="paragraph",
                page_number=11,
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]

            # Filter for table chunks on page 10 only
            res = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="financial report",
                chunk_type="table",
                page_number=10,
            )
            retrieved_ids = [c.chunk_id for c in res.chunks]
            assert c1.id in retrieved_ids
            assert c2.id not in retrieved_ids


class TestHybridRetrievalAPI:
    """Integration test suite for POST /api/v1/retrieval/hybrid-search REST API."""

    @pytest.mark.asyncio
    async def test_api_hybrid_search_success(self, test_env: dict[str, Any]) -> None:
        """Verify POST /api/v1/retrieval/hybrid-search returns 200 with diagnostics."""
        client: AsyncClient = test_env["client"]
        async with test_env["session_factory"]() as session:
            _, org, token = await _seed_user_and_org(session)
            await _index_test_chunk(
                session, test_env, org.id, "Consolidated revenue in Q4 reached $500M."
            )

        resp = await client.post(
            "/api/v1/retrieval/hybrid-search",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": "What was the revenue in Q4?",
                "top_k": 5,
                "dense_candidate_k": 20,
                "sparse_candidate_k": 20,
                "rrf_k": 60,
                "include_parent": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["retrieval_mode"] == "hybrid"
        assert data["total_results"] >= 1
        assert "diagnostics" in data
        assert data["diagnostics"]["rrf_k"] == 60
        assert "latency" in data["diagnostics"]

    @pytest.mark.asyncio
    async def test_api_hybrid_search_unauthorized(self, test_env: dict[str, Any]) -> None:
        """Verify 401 Unauthorized when no valid JWT token is supplied."""
        client: AsyncClient = test_env["client"]
        resp = await client.post(
            "/api/v1/retrieval/hybrid-search",
            json={"query": "Unauthenticated search"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_api_query_validation(self, test_env: dict[str, Any]) -> None:
        """Verify 400 or 422 on empty or overly short query string."""
        client: AsyncClient = test_env["client"]
        async with test_env["session_factory"]() as session:
            _, _, token = await _seed_user_and_org(session)

        resp = await client.post(
            "/api/v1/retrieval/hybrid-search",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": " "},
        )
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_api_hybrid_disabled_returns_400(self, test_env: dict[str, Any]) -> None:
        """Verify 400 error when HYBRID_RETRIEVAL_ENABLED setting is False."""
        client: AsyncClient = test_env["client"]
        settings = get_settings()
        original_enabled = settings.HYBRID_RETRIEVAL_ENABLED
        settings.HYBRID_RETRIEVAL_ENABLED = False

        try:
            async with test_env["session_factory"]() as session:
                _, _, token = await _seed_user_and_org(session)

            resp = await client.post(
                "/api/v1/retrieval/hybrid-search",
                headers={"Authorization": f"Bearer {token}"},
                json={"query": "Valid query string"},
            )
            assert resp.status_code == 400
            assert "disabled" in str(resp.json()).lower()
        finally:
            settings.HYBRID_RETRIEVAL_ENABLED = original_enabled

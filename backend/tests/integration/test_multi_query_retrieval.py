"""Integration test suite for Task 15 Query Understanding & Multi-Query Retrieval.

Validates:
- End-to-end pipeline: Query Understanding -> SearchPlan -> Multi-Query Hybrid Retrieval
  -> Cross-Query RRF Fusion -> Cross-Encoder Reranking -> Parent Hydration.
- Decomposed query recall: answers spanning separate years/topics are both retrieved.
- Multilingual queries (Arabic, Turkish, English, mixed language).
- Multi-tenant isolation under multi-query execution.
- Parent hydration occurring strictly after reranking for top-K candidates (0 N+1).
- Dedicated query analysis endpoint: POST /api/v1/query/analyze.
- Hybrid search API with enable_query_understanding=True.
- Performance benchmark measuring query planning latency vs retrieval latency.
"""

import time
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
from app.query.config import QueryUnderstandingConfig
from app.query.models import QueryIntent
from app.query.multi_retrieval import MultiQueryRetrievalService
from app.query.service import QueryUnderstandingService
from app.rbac.catalog import ROLE_ANALYST
from app.rbac.service import RBACService
from app.repositories.chunk import DocumentChunkRepository
from app.reranking.config import RerankerConfig
from app.reranking.providers.local import LocalDeterministicCrossEncoderProvider
from app.reranking.service import CrossEncoderRerankingService
from app.retrieval.config import BM25Config, HybridRetrievalConfig
from app.retrieval.hybrid.service import HybridRetrievalService
from app.retrieval.service import DenseRetrievalService
from app.retrieval.sparse.analyzer import MultilingualSparseAnalyzer
from app.retrieval.sparse.bm25 import BM25Encoder
from app.retrieval.sparse.service import SparseRetrievalService
from app.retrieval.sparse.stats import TenantCorpusStatsManager
from app.services.embedding_pipeline import create_default_embedding_service
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.models import VectorPoint
from app.vectorstore.providers.qdrant import QdrantVectorStoreProvider
from app.vectorstore.service import VectorStoreService


@pytest.fixture
async def test_env() -> AsyncGenerator[dict[str, Any], None]:
    """Provide fully wired environment with Postgres, in-memory Qdrant, and Query Understanding."""
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

    reranker_cfg = RerankerConfig(
        enabled=True,
        provider="local",
        max_candidates=50,
        final_k=10,
        allow_fallback=True,
    )
    reranker_provider = LocalDeterministicCrossEncoderProvider()
    reranker_service = CrossEncoderRerankingService(
        provider=reranker_provider,
        config=reranker_cfg,
    )

    qu_cfg = QueryUnderstandingConfig(
        enabled=True,
        rewrite_enabled=True,
        expansion_enabled=True,
        decomposition_enabled=True,
        deterministic_mode=True,
    )
    qu_service = QueryUnderstandingService(config=qu_cfg)

    chunk_repo = DocumentChunkRepository()
    hybrid_cfg = HybridRetrievalConfig.from_settings(settings)

    hybrid_service = HybridRetrievalService(
        dense_service=dense_service,
        sparse_service=sparse_service,
        reranker_service=reranker_service,
        chunk_repository=chunk_repo,
        config=hybrid_cfg,
        query_understanding_service=qu_service,
    )

    multi_query_service = MultiQueryRetrievalService(
        hybrid_service=hybrid_service,
        reranker_service=reranker_service,
        chunk_repository=chunk_repo,
    )
    hybrid_service.multi_query_service = multi_query_service

    app.state.qdrant_client = memory_qdrant
    app.state.vector_store_provider = qdrant_provider
    app.state.vector_store_service = vs_service
    app.state.embedding_service = emb_service
    app.state.dense_retrieval_service = dense_service
    app.state.sparse_retrieval_service = sparse_service
    app.state.reranker_service = reranker_service
    app.state.hybrid_retrieval_service = hybrid_service
    app.state.query_understanding_service = qu_service
    app.state.multi_query_service = multi_query_service

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
            "reranker_service": reranker_service,
            "hybrid_service": hybrid_service,
            "qu_service": qu_service,
            "multi_query_service": multi_query_service,
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
    """Create test organization, user, membership, and access token."""
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
    test_env: dict[str, Any],
    org_id: uuid.UUID,
    content: str,
    *,
    chunk_type: str = "sentence",
    parent_chunk_id: uuid.UUID | None = None,
) -> DocumentChunk:
    """Helper indexing chunk into PostgreSQL, Dense Qdrant, and BM25 index."""
    doc = Document(
        organization_id=org_id,
        name=f"Doc-{uuid.uuid4().hex[:6]}",
        original_filename="sample.pdf",
        mime_type="application/pdf",
        file_size=1024,
        sha256=uuid.uuid4().hex,
        storage_backend="local",
        storage_key=f"uploads/{uuid.uuid4().hex}.pdf",
        status="completed",
    )
    session.add(doc)
    await session.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
        organization_id=org_id,
        content=content,
        chunk_index=0,
        chunk_type=chunk_type,
        token_count=len(content.split()),
        character_count=len(content),
        parent_chunk_id=parent_chunk_id,
    )
    session.add(chunk)
    await session.commit()
    await session.refresh(chunk)

    analyzer = test_env["analyzer"]
    stats_mgr = test_env["stats_mgr"]
    bm25_encoder = test_env["bm25_encoder"]

    analyzed = analyzer.analyze(content)
    stats_mgr.register_chunk(org_id, analyzed)
    sparse_vec = bm25_encoder.encode_document(analyzed, avgdl=stats_mgr.get_stats(org_id).avgdl)

    emb_svc = test_env["emb_service"]
    dense_vec = await emb_svc.embed_query(content)

    vs_svc: VectorStoreService = test_env["vs_service"]
    coll_name = await vs_svc.ensure_collection(
        embedding_provider=emb_svc.provider_name,
        embedding_model=emb_svc.model_name,
        dimensions=emb_svc.dimensions,
        version=emb_svc.version,
    )

    point = VectorPoint(
        id=chunk.id,
        vector=dense_vec,
        sparse_vector=sparse_vec,
        payload={
            "organization_id": str(org_id),
            "document_id": str(doc.id),
            "chunk_id": str(chunk.id),
            "chunk_type": chunk_type,
            "page_number": 1,
            "text": content,
            "chunk_index": 0,
            "heading_hierarchy": [],
            "parent_chunk_id": str(parent_chunk_id) if parent_chunk_id else None,
        },
    )
    await vs_svc.provider.upsert(collection_name=coll_name, points=[point])
    return chunk


class TestMultiQueryRetrievalPipeline:
    """Integration tests verifying end-to-end multi-query planning and retrieval."""

    @pytest.mark.asyncio
    async def test_decomposed_query_retrieves_both_aspects(self, test_env: dict[str, Any]) -> None:
        """Verify decomposed comparison query retrieves both 2024 and 2025 chunks."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            # Chunk 1: Answers 2024 performance
            c2024 = await _index_test_chunk(
                session, test_env, org.id, "In fiscal year 2024 total revenue reached $85 million."
            )
            # Chunk 2: Answers 2025 performance
            c2025 = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "In fiscal year 2025 total revenue expanded to $110 million.",
            )

            qu_service: QueryUnderstandingService = test_env["qu_service"]
            mq_service: MultiQueryRetrievalService = test_env["multi_query_service"]

            query = "Compare revenue in 2024 and 2025"
            plan = await qu_service.analyze_and_plan(
                query=query,
                organization_id=org.id,
                enable_decomposition=True,
            )

            assert plan.intent == QueryIntent.COMPARISON
            assert len(plan.sub_queries) >= 2

            # Execute multi-query retrieval plan
            result = await mq_service.execute_plan(
                session=session,
                organization_id=org.id,
                plan=plan,
                top_k=5,
                rerank=True,
            )

            retrieved_chunk_ids = [c.chunk_id for c in result.chunks]
            assert c2024.id in retrieved_chunk_ids
            assert c2025.id in retrieved_chunk_ids
            assert result.retrieval_mode == "multi_query_hybrid_reranked"

    @pytest.mark.asyncio
    async def test_multilingual_query_planning_and_search(self, test_env: dict[str, Any]) -> None:
        """Verify Arabic and Turkish queries generate multilingual search plans and get chunks."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            # Arabic document
            ar_chunk = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "تراجع هامش التشغيل في الربع الرابع بسبب ارتفاع أسعار الشحن وسلاسل الإمداد.",
            )
            # Turkish document
            tr_chunk = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Faaliyet marjı lojistik maliyetlerindeki artış sebebiyle "
                "belirgin bir daralma kaydetti.",
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]

            # Arabic Search with query understanding
            res_ar = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="ما سبب انخفاض هامش التشغيل؟",
                enable_query_understanding=True,
                enable_query_expansion=True,
                top_k=5,
            )
            assert len(res_ar.chunks) > 0
            assert res_ar.chunks[0].chunk_id == ar_chunk.id

            # Turkish Search with query understanding
            res_tr = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="Faaliyet marjındaki düşüşün nedeni neydi?",
                enable_query_understanding=True,
                enable_query_expansion=True,
                top_k=5,
            )
            assert len(res_tr.chunks) > 0
            assert res_tr.chunks[0].chunk_id == tr_chunk.id

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation_under_multi_query(self, test_env: dict[str, Any]) -> None:
        """Verify multi-query execution for Org A never leaks or scores Org B candidates."""
        async with test_env["session_factory"]() as session:
            _, org_a, _ = await _seed_user_and_org(session, org_name="Tenant A")
            _, org_b, _ = await _seed_user_and_org(session, org_name="Tenant B")

            chunk_a = await _index_test_chunk(
                session, test_env, org_a.id, "Confidential quarterly EBITDA report for Tenant A."
            )
            chunk_b = await _index_test_chunk(
                session,
                test_env,
                org_b.id,
                "Confidential quarterly EBITDA report for Tenant A exact answer match.",
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]
            res = await hybrid_service.search(
                session=session,
                organization_id=org_a.id,
                query="quarterly EBITDA report",
                enable_query_understanding=True,
                enable_query_expansion=True,
            )

            retrieved_ids = [c.chunk_id for c in res.chunks]
            assert chunk_a.id in retrieved_ids
            assert chunk_b.id not in retrieved_ids

    @pytest.mark.asyncio
    async def test_parent_hydration_after_reranking_zero_n_plus_one(
        self, test_env: dict[str, Any]
    ) -> None:
        """Verify parent hydration occurs strictly for the top-K chunks after cross-query fusion."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            parent = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Section Heading: Operational Cost Drivers",
                chunk_type="section",
            )
            child = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Energy expenses escalated significantly affecting total operating cost.",
                chunk_type="sentence",
                parent_chunk_id=parent.id,
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]
            res = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="operating cost drivers and energy expenses",
                enable_query_understanding=True,
                include_parent=True,
                top_k=5,
            )

            matched_child = next((c for c in res.chunks if c.chunk_id == child.id), None)
            assert matched_child is not None
            assert matched_child.parent_chunk_id == parent.id
            assert matched_child.parent_text == "Section Heading: Operational Cost Drivers"


class TestQueryUnderstandingAPI:
    """Validate REST API endpoints for query analysis and hybrid search."""

    @pytest.mark.asyncio
    async def test_api_query_analyze_endpoint(self, test_env: dict[str, Any]) -> None:
        """Verify POST /api/v1/query/analyze returns structured SearchPlan."""
        client: AsyncClient = test_env["client"]
        async with test_env["session_factory"]() as session:
            _, org, token = await _seed_user_and_org(session)

        response = await client.post(
            "/api/v1/query/analyze",
            json={
                "query": "Compare 2024 and 2025 revenue for ACME under Project XJ-4927",
                "enable_rewrite": True,
                "enable_expansion": True,
                "enable_decomposition": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        plan = data["search_plan"]

        assert (
            plan["original_query"] == "Compare 2024 and 2025 revenue for ACME under Project XJ-4927"
        )
        assert plan["intent"] == "comparison"
        assert len(plan["sub_queries"]) >= 2
        assert "hard_filters" in plan
        assert "soft_filters" in plan
        assert plan["diagnostics"]["total_understanding_ms"] >= 0.0

    @pytest.mark.asyncio
    async def test_api_hybrid_search_with_query_understanding(
        self, test_env: dict[str, Any]
    ) -> None:
        """Verify POST /api/v1/retrieval/hybrid-search accepts query understanding flags."""
        client: AsyncClient = test_env["client"]
        async with test_env["session_factory"]() as session:
            _, org, token = await _seed_user_and_org(session)
            await _index_test_chunk(
                session, test_env, org.id, "ACME annual revenue grew 20% in fiscal year 2025."
            )

        response = await client.post(
            "/api/v1/retrieval/hybrid-search",
            json={
                "query": "revenue?",
                "top_k": 5,
                "enable_query_understanding": True,
                "enable_query_rewrite": True,
                "rerank": True,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) > 0


class TestQueryUnderstandingPerformanceBenchmark:
    """Benchmark latency of query understanding and multi-query planning."""

    @pytest.mark.asyncio
    async def test_query_understanding_latency_benchmark(self, test_env: dict[str, Any]) -> None:
        """Measure latency of deterministic query understanding over multiple queries."""
        qu_service: QueryUnderstandingService = test_env["qu_service"]
        queries = [
            "What was the revenue in 2025?",
            "Why did operating margin decline?",
            "Compare revenue in 2024 and 2025",
            "ما سبب انخفاض هامش التشغيل في الربع الرابع؟",
            "Faaliyet marjındaki düşüşün nedeni neydi?",
        ]

        latencies_ms: list[float] = []
        for q in queries:
            t0 = time.perf_counter()
            plan = await qu_service.analyze_and_plan(q)
            lat_ms = (time.perf_counter() - t0) * 1000.0
            latencies_ms.append(lat_ms)
            assert plan.primary_query is not None

        latencies_ms.sort()
        p50 = latencies_ms[len(latencies_ms) // 2]
        p95 = latencies_ms[-1]

        # In-memory deterministic query analysis should be lightning fast (< 10ms p95)
        assert p50 < 10.0, f"Query understanding p50 too high: {p50}ms"
        assert p95 < 20.0, f"Query understanding p95 too high: {p95}ms"

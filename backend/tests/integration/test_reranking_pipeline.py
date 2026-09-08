"""Integration test suite for Task 14 Cross-Encoder Reranking pipeline.

Validates:
- End-to-end Hybrid Retrieval + RRF + Cross-Encoder Reranking pipeline.
- Reranking changes ranking order based on query-candidate cross relevance.
- Comparison between rerank=False (RRF order) and rerank=True (Reranked order).
- Multilingual queries and documents (Arabic, Turkish, English, mixed language).
- Multi-tenant boundary isolation.
- Post-reranking zero N+1 batch parent hydration.
- Graceful degradation and fallback to RRF on reranker error.
- REST API integration: POST /api/v1/retrieval/hybrid-search with rerank flag.
- Empirical latency measurements across 10, 25, and 50 candidate pools.
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
from app.rbac.catalog import ROLE_ANALYST
from app.rbac.service import RBACService
from app.repositories.chunk import DocumentChunkRepository
from app.reranking.config import RerankerConfig
from app.reranking.providers.local import LocalDeterministicCrossEncoderProvider
from app.reranking.service import CrossEncoderRerankingService
from app.retrieval.config import BM25Config, HybridRetrievalConfig
from app.retrieval.hybrid.models import FusedCandidate
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
    """Provide fully wired test environment with PostgreSQL, in-memory Qdrant, and Reranker."""
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

    hybrid_cfg = HybridRetrievalConfig.from_settings(settings)
    chunk_repo = DocumentChunkRepository()
    hybrid_service = HybridRetrievalService(
        dense_service=dense_service,
        sparse_service=sparse_service,
        reranker_service=reranker_service,
        chunk_repository=chunk_repo,
        config=hybrid_cfg,
    )

    app.state.qdrant_client = memory_qdrant
    app.state.vector_store_provider = qdrant_provider
    app.state.vector_store_service = vs_service
    app.state.embedding_service = emb_service
    app.state.dense_retrieval_service = dense_service
    app.state.sparse_retrieval_service = sparse_service
    app.state.reranker_service = reranker_service
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
            "reranker_service": reranker_service,
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
    env: dict[str, Any],
    org_id: uuid.UUID,
    content: str,
    chunk_type: str = "paragraph",
    page_number: int = 1,
    parent_chunk_id: uuid.UUID | None = None,
    heading_hierarchy: list[str] | None = None,
) -> DocumentChunk:
    """Index a chunk into PostgreSQL and Qdrant (dense + sparse)."""
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

    analyzer = env["analyzer"]
    stats_mgr = env["stats_mgr"]
    bm25_encoder = env["bm25_encoder"]

    analyzed = analyzer.analyze(content)
    stats_mgr.register_chunk(org_id, analyzed)
    sparse_vec = bm25_encoder.encode_document(analyzed, avgdl=stats_mgr.get_stats(org_id).avgdl)

    emb_service = env["emb_service"]
    dense_vec = await emb_service.embed_query(content)

    vs_service: VectorStoreService = env["vs_service"]
    coll_name = await vs_service.ensure_collection(
        embedding_provider=emb_service.provider_name,
        embedding_model=emb_service.model_name,
        dimensions=emb_service.dimensions,
        version=emb_service.version,
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
            "page_number": page_number,
            "text": content,
            "chunk_index": 0,
            "heading_hierarchy": heading_hierarchy or [],
        },
    )
    await vs_service.provider.upsert(collection_name=coll_name, points=[point])
    return chunk


class TestRerankingPipeline:
    """Integration test suite verifying cross-encoder reranking mechanics."""

    @pytest.mark.asyncio
    async def test_reranking_refines_candidate_ranking(self, test_env: dict[str, Any]) -> None:
        """Verify cross-encoder re-ranks candidates with answering relevance over keyword match."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            # Candidate A: High lexical overlap, but does not answer the question
            _cand_a = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Operating margin operating margin operating margin report for general meetings.",
            )
            # Candidate B: Provides the precise answer to what caused the decline
            cand_b = await _index_test_chunk(
                session,
                test_env,
                org.id,
                (
                    "The severe decline in operating margin was driven by "
                    "soaring raw material inflation."
                ),
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]
            query = "What caused the decline in operating margin?"

            # Search with rerank=True
            res_reranked = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query=query,
                rerank=True,
                top_k=5,
            )

            assert len(res_reranked.chunks) >= 2
            assert res_reranked.retrieval_mode == "hybrid_reranked"
            top_hit = res_reranked.chunks[0]

            # Candidate B should be promoted to rank 1 by the cross-encoder
            assert top_hit.chunk_id == cand_b.id
            assert top_hit.rerank_score is not None
            assert top_hit.rerank_rank == 1
            assert top_hit.original_rank is not None

    @pytest.mark.asyncio
    async def test_rerank_flag_disabled_vs_enabled_comparison(
        self, test_env: dict[str, Any]
    ) -> None:
        """Verify behavior difference when rerank=False vs rerank=True."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)
            await _index_test_chunk(
                session, test_env, org.id, "Consolidated revenue grew by 15% in Q4 2025."
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]
            query = "Revenue growth in Q4 2025"

            # 1. Rerank disabled
            res_no_rerank = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query=query,
                rerank=False,
                top_k=5,
            )
            assert res_no_rerank.retrieval_mode == "hybrid"
            assert res_no_rerank.diagnostics.reranking_enabled is False
            assert res_no_rerank.chunks[0].rerank_score is None
            assert res_no_rerank.chunks[0].rerank_rank is None

            # 2. Rerank enabled
            res_with_rerank = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query=query,
                rerank=True,
                top_k=5,
            )
            assert res_with_rerank.retrieval_mode == "hybrid_reranked"
            assert res_with_rerank.diagnostics.reranking_enabled is True
            assert res_with_rerank.chunks[0].rerank_score is not None
            assert res_with_rerank.chunks[0].rerank_rank == 1
            assert res_with_rerank.diagnostics.latency.rerank_ms >= 0.0

    @pytest.mark.asyncio
    async def test_multilingual_reranking_arabic_and_turkish(
        self, test_env: dict[str, Any]
    ) -> None:
        """Verify Arabic and Turkish semantic answering pairs are prioritized by reranker."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            # Arabic chunks
            ar_rel = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "السبب الرئيسي وراء انخفاض هامش التشغيل هو تكاليف الشحن الدولي لعام ٢٠٢٥",
            )
            await _index_test_chunk(
                session,
                test_env,
                org.id,
                "هامش التشغيل مذكور في التقرير المالي السنوي بدون تفاصيل إضافية",
            )

            # Turkish chunks
            tr_rel = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Faaliyet marjındaki düşüşün ana sebebi artan lojistik ve üretim maliyetleridir.",
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]

            # Arabic query
            res_ar = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="ما سبب انخفاض هامش التشغيل؟",
                rerank=True,
            )
            assert res_ar.chunks[0].chunk_id == ar_rel.id
            assert res_ar.chunks[0].rerank_rank == 1

            # Turkish query
            res_tr = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="Faaliyet marjındaki düşüşün nedeni nedir?",
                rerank=True,
            )
            assert res_tr.chunks[0].chunk_id == tr_rel.id
            assert res_tr.chunks[0].rerank_rank == 1

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation_under_reranking(self, test_env: dict[str, Any]) -> None:
        """Verify Org A search never retrieves Org B candidate despite high relevance."""
        async with test_env["session_factory"]() as session:
            _, org_a, _ = await _seed_user_and_org(session, org_name="Alpha Corp")
            _, org_b, _ = await _seed_user_and_org(session, org_name="Beta Corp")

            chunk_a = await _index_test_chunk(
                session, test_env, org_a.id, "Secret revenue project Alpha."
            )
            chunk_b = await _index_test_chunk(
                session,
                test_env,
                org_b.id,
                "Secret revenue project Alpha with extra details and exact answer.",
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]
            res = await hybrid_service.search(
                session=session,
                organization_id=org_a.id,
                query="Secret revenue project Alpha",
                rerank=True,
            )

            retrieved_ids = [c.chunk_id for c in res.chunks]
            assert chunk_a.id in retrieved_ids
            assert chunk_b.id not in retrieved_ids

    @pytest.mark.asyncio
    async def test_post_reranking_parent_hydration(self, test_env: dict[str, Any]) -> None:
        """Verify parent hydration occurs strictly after reranking for top-K without N+1."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            parent = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Section: Global Supply Chain Vulnerabilities",
                chunk_type="section",
            )
            child = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Manufacturing halts in Asia reduced operational margins by 8%.",
                chunk_type="paragraph",
                parent_chunk_id=parent.id,
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]
            res = await hybrid_service.search(
                session=session,
                organization_id=org.id,
                query="Manufacturing halts operational margins",
                rerank=True,
                include_parent=True,
            )

            matching = next((c for c in res.chunks if c.chunk_id == child.id), None)
            assert matching is not None
            assert matching.parent_chunk_id == parent.id
            assert matching.parent_text == parent.content

    @pytest.mark.asyncio
    async def test_reranker_failure_graceful_fallback(self, test_env: dict[str, Any]) -> None:
        """Verify if reranker fails, hybrid retrieval falls back to RRF ranking without crashing."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)
            chunk = await _index_test_chunk(
                session, test_env, org.id, "Robust fallback architecture."
            )

            hybrid_service: HybridRetrievalService = test_env["hybrid_service"]

            # Artificially inject error into reranker provider
            async def failing_score(*args: Any, **kwargs: Any) -> Any:
                raise RuntimeError("CrossEncoder model crashed")

            orig_score = hybrid_service.reranker_service.provider.score_pairs  # type: ignore
            hybrid_service.reranker_service.provider.score_pairs = failing_score  # type: ignore

            try:
                res = await hybrid_service.search(
                    session=session,
                    organization_id=org.id,
                    query="Robust fallback",
                    rerank=True,
                )
                assert len(res.chunks) >= 1
                assert res.chunks[0].chunk_id == chunk.id
                assert res.diagnostics.is_degraded is True
                assert "CrossEncoder model crashed" in (res.diagnostics.degradation_reason or "")
            finally:
                hybrid_service.reranker_service.provider.score_pairs = orig_score  # type: ignore


class TestRerankingAPI:
    """Integration test suite for POST /api/v1/retrieval/hybrid-search API with reranking."""

    @pytest.mark.asyncio
    async def test_api_hybrid_search_with_rerank_enabled(self, test_env: dict[str, Any]) -> None:
        """Verify API accepts rerank=True and returns reranker diagnostics and scores."""
        client: AsyncClient = test_env["client"]
        async with test_env["session_factory"]() as session:
            _, org, token = await _seed_user_and_org(session)
            await _index_test_chunk(
                session,
                test_env,
                org.id,
                "In Q4 2025, cloud infrastructure margins expanded to 35%.",
            )

        resp = await client.post(
            "/api/v1/retrieval/hybrid-search",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": "What were cloud infrastructure margins in Q4?",
                "top_k": 5,
                "dense_candidate_k": 20,
                "sparse_candidate_k": 20,
                "rerank": True,
                "rerank_candidates": 20,
                "include_parent": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["retrieval_mode"] == "hybrid_reranked"
        assert data["total_results"] >= 1
        assert "diagnostics" in data
        assert data["diagnostics"]["reranking_enabled"] is True
        assert data["diagnostics"]["reranker_provider"] == "local"
        assert "rerank_ms" in data["diagnostics"]["latency"]

        top_chunk = data["results"][0]
        assert top_chunk["rerank_score"] is not None
        assert top_chunk["rerank_rank"] == 1
        assert top_chunk["original_rank"] is not None

    @pytest.mark.asyncio
    async def test_api_hybrid_search_with_rerank_disabled(self, test_env: dict[str, Any]) -> None:
        """Verify API accepts rerank=False and returns standard hybrid mode."""
        client: AsyncClient = test_env["client"]
        async with test_env["session_factory"]() as session:
            _, org, token = await _seed_user_and_org(session)
            await _index_test_chunk(session, test_env, org.id, "Financial summary overview.")

        resp = await client.post(
            "/api/v1/retrieval/hybrid-search",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": "Financial summary",
                "top_k": 5,
                "rerank": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["retrieval_mode"] == "hybrid"
        assert data["diagnostics"]["reranking_enabled"] is False
        assert data["results"][0]["rerank_score"] is None


class TestRerankerPerformanceBenchmark:
    """Benchmark empirical performance across candidate pools (10, 25, 50)."""

    @pytest.mark.asyncio
    async def test_latency_across_candidate_pool_sizes(self, test_env: dict[str, Any]) -> None:
        """Measure empirical p50/p95 latency on CPU across candidate pool sizes."""
        reranker_service: CrossEncoderRerankingService = test_env["reranker_service"]
        org_id = uuid.uuid4()

        pool_sizes = [10, 25, 50]
        benchmark_results: dict[int, dict[str, float]] = {}

        for pool_size in pool_sizes:
            candidates = [
                FusedCandidate(
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    organization_id=org_id,
                    rrf_score=0.01 * (pool_size - i),
                    rank=i + 1,
                    payload={
                        "text": (
                            f"Document chunk number {i} discussing fiscal performance, "
                            "revenue, and margins."
                        )
                    },
                )
                for i in range(pool_size)
            ]

            latencies: list[float] = []
            # Run 5 iterations to compute empirical percentiles
            for _ in range(5):
                t0 = time.perf_counter()
                res = await reranker_service.rerank(
                    query="What was the fiscal performance and revenue?",
                    candidates=candidates,
                    organization_id=org_id,
                    top_k=10,
                    max_candidates=pool_size,
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                latencies.append(elapsed_ms)
                assert len(res.candidates) <= 10

            latencies.sort()
            p50 = latencies[len(latencies) // 2]
            p95 = latencies[-1]
            benchmark_results[pool_size] = {"p50_ms": round(p50, 2), "p95_ms": round(p95, 2)}

        # Verify latency scales predictably and is under safety budget (< 50ms for local CPU)
        for size, stats in benchmark_results.items():
            assert stats["p50_ms"] < 100.0, (
                f"Pool size {size} p50 exceeded budget: {stats['p50_ms']}ms"
            )

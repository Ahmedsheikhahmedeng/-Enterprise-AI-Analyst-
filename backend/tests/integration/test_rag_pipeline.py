"""Integration test suite for Task 16 Evidence-Grounded RAG & Answer Generation."""

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
from app.models.analysis import AnalysisRun, AnalysisStep
from app.models.document import Document, DocumentChunk
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.usage import LLMRequest, UsageEvent
from app.models.user import User
from app.query.config import QueryUnderstandingConfig
from app.query.multi_retrieval import MultiQueryRetrievalService
from app.query.service import QueryUnderstandingService
from app.rag.config import RAGConfig
from app.rag.providers.local import LocalDeterministicAnswerProvider
from app.rag.service import RAGService
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
    """Provide fully wired test environment with RAGService, in-memory Qdrant, and Postgres."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

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

    rag_cfg = RAGConfig(
        enabled=True,
        provider="deterministic",
        model="deterministic-rag-v1",
        api_key=None,
        base_url=None,
        temperature=0.0,
        max_output_tokens=1024,
        max_context_tokens=4000,
        evidence_top_k=5,
        min_evidence_score=0.0,
        timeout_seconds=30.0,
        max_retries=2,
        prompt_version="v1",
        response_language="auto",
        max_cost_per_request=0.10,
    )
    rag_provider = LocalDeterministicAnswerProvider(model_name="deterministic-rag-v1")
    rag_service = RAGService(
        hybrid_retrieval_service=hybrid_service,
        query_understanding_service=qu_service,
        provider=rag_provider,
        config=rag_cfg,
    )

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
    app.state.rag_service = rag_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield {
            "app": app,
            "client": client,
            "session_factory": session_factory,
            "vs_service": vs_service,
            "emb_service": emb_service,
            "hybrid_service": hybrid_service,
            "qu_service": qu_service,
            "rag_service": rag_service,
            "stats_mgr": stats_mgr,
            "analyzer": analyzer,
            "bm25_encoder": bm25_encoder,
        }

    await memory_qdrant.close()
    await dispose_database_engine(engine)


async def _seed_user_and_org(
    session: AsyncSession,
    org_name: str = "Test Org",
    role_name: str = ROLE_ANALYST,
) -> tuple[User, Organization, str]:
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
    document_name: str = "financial_statement.pdf",
    page_number: int = 1,
) -> DocumentChunk:
    doc = Document(
        organization_id=org_id,
        name=document_name,
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
            "page_number": page_number,
            "text": content,
            "chunk_index": 0,
            "heading_hierarchy": ["Financial Summary", "Revenues"],
            "document_name": document_name,
            "metadata": {"document_name": document_name},
            "parent_chunk_id": str(parent_chunk_id) if parent_chunk_id else None,
        },
    )
    await vs_svc.provider.upsert(collection_name=coll_name, points=[point])
    return chunk


class TestRAGPipelineIntegration:
    """Integration tests for evidence-grounded RAG answer generation."""

    @pytest.mark.asyncio
    async def test_end_to_end_grounded_answer(self, test_env: dict[str, Any]) -> None:
        """Verify indexed financial statement generates factual answer with valid [E1] citation."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)
            chunk = await _index_test_chunk(
                session,
                test_env,
                org.id,
                "In fiscal year 2025 operating revenue expanded to $110 million.",
                document_name="Annual_Report_2025.pdf",
                page_number=8,
            )

            rag_service: RAGService = test_env["rag_service"]
            result = await rag_service.answer(
                query="What was total operating revenue in 2025?",
                organization_id=org.id,
                session=session,
            )

            assert result.answer.grounded is True
            assert result.answer.confidence >= 0.8
            assert "[E1]" in result.answer.answer
            assert len(result.answer.citations) == 1
            cit = result.answer.citations[0]
            assert cit.evidence_id == "E1"
            assert cit.chunk_id == chunk.id
            assert cit.document_id == chunk.document_id
            assert cit.page_number == 8
            assert "Annual_Report_2025.pdf" in str(cit.document_name)

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation_under_rag(self, test_env: dict[str, Any]) -> None:
        """Verify Organization A cannot access or cite Organization B evidence under RAG."""
        async with test_env["session_factory"]() as session:
            _, org_a, _ = await _seed_user_and_org(session, org_name="Org A")
            _, org_b, _ = await _seed_user_and_org(session, org_name="Org B")

            # Index secret data in Org B only
            chunk_b = await _index_test_chunk(
                session,
                test_env,
                org_b.id,
                "Project Alpha proprietary acquisition budget is $500 million.",
                document_name="OrgB_Secret.pdf",
            )

            rag_service: RAGService = test_env["rag_service"]
            # User from Org A queries about Project Alpha
            res_a = await rag_service.answer(
                query="What is the proprietary budget for Project Alpha?",
                organization_id=org_a.id,
                session=session,
            )

            # Org A must not see Org B data in answer or evidence
            assert res_a.answer.grounded is False
            assert all(ev.chunk_id != chunk_b.id for ev in res_a.evidence)
            assert all(ev.organization_id == org_a.id for ev in res_a.evidence)

    @pytest.mark.asyncio
    async def test_multilingual_grounded_rag(self, test_env: dict[str, Any]) -> None:
        """Verify Arabic and Turkish questions retrieve multilingual evidence and cite properly."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            # Arabic document
            await _index_test_chunk(
                session,
                test_env,
                org.id,
                "تراجع هامش التشغيل في الربع الرابع بسبب ارتفاع أسعار الشحن وسلاسل الإمداد.",
                document_name="ar_report.pdf",
            )
            # Turkish document
            await _index_test_chunk(
                session,
                test_env,
                org.id,
                (
                    "Faaliyet marjı lojistik maliyetlerindeki artış sebebiyle "
                    "belirgin bir daralma kaydetti."
                ),
                document_name="tr_report.pdf",
            )

            rag_service: RAGService = test_env["rag_service"]

            # Arabic query
            res_ar = await rag_service.answer(
                query="ما سبب تراجع هامش التشغيل؟",
                organization_id=org.id,
                session=session,
            )
            assert res_ar.answer.grounded is True
            assert "[E1]" in res_ar.answer.answer
            assert len(res_ar.answer.citations) >= 1

            # Turkish query
            res_tr = await rag_service.answer(
                query="Faaliyet marjı neden daraldı?",
                organization_id=org.id,
                session=session,
            )
            assert res_tr.answer.grounded is True
            assert "[E1]" in res_tr.answer.answer
            assert len(res_tr.answer.citations) >= 1

    @pytest.mark.asyncio
    async def test_contradictory_evidence_handling(self, test_env: dict[str, Any]) -> None:
        """Verify contradictory evidence produces conflicting acknowledgment citing both sources."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            await _index_test_chunk(
                session,
                test_env,
                org.id,
                "According to the preliminary audit, total revenue was $100 million in Q4.",
                document_name="preliminary.pdf",
            )
            await _index_test_chunk(
                session,
                test_env,
                org.id,
                "According to final audited accounts, total revenue was $120 million in Q4.",
                document_name="final_audit.pdf",
            )

            rag_service: RAGService = test_env["rag_service"]
            res = await rag_service.answer(
                query="What was revenue in Q4?",
                organization_id=org.id,
                session=session,
            )

            assert res.answer.grounded is True
            assert res.answer.is_contradictory is True
            assert "conflicting" in res.answer.answer.lower()
            assert len(res.answer.citations) >= 2

    @pytest.mark.asyncio
    async def test_unsupported_question_no_hallucination(self, test_env: dict[str, Any]) -> None:
        """Verify asking about unsupported facts returns grounded=false
        with no phantom citations.
        """
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)
            await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Company operational expenses totaled $10 million in 2025.",
            )

            rag_service: RAGService = test_env["rag_service"]
            res = await rag_service.answer(
                query="What is the CEO's favorite food?",
                organization_id=org.id,
                session=session,
            )

            assert res.answer.grounded is False
            assert len(res.answer.citations) == 0
            assert res.answer.confidence <= 0.3

    @pytest.mark.asyncio
    async def test_empty_retrieval_fast_exit(self, test_env: dict[str, Any]) -> None:
        """Verify empty corpus leads to zero LLM latency fast exit."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)

            rag_service: RAGService = test_env["rag_service"]
            res = await rag_service.answer(
                query="What is revenue in completely empty index?",
                organization_id=org.id,
                session=session,
            )

            assert res.answer.grounded is False
            assert res.diagnostics.llm_latency_ms == 0.0
            assert len(res.evidence) == 0

    @pytest.mark.asyncio
    async def test_persistence_telemetry(self, test_env: dict[str, Any]) -> None:
        """Verify AnalysisStep, LLMRequest, and UsageEvent are persisted when run_id is supplied."""
        async with test_env["session_factory"]() as session:
            from sqlalchemy import select

            user, org, _ = await _seed_user_and_org(session)
            await _index_test_chunk(
                session,
                test_env,
                org.id,
                "In fiscal year 2025 total revenue reached $150 million.",
            )

            run = AnalysisRun(
                organization_id=org.id,
                user_id=user.id,
                query="What was revenue in 2025?",
                status="running",
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)

            rag_service: RAGService = test_env["rag_service"]
            await rag_service.answer(
                query="What was revenue in 2025?",
                organization_id=org.id,
                session=session,
                user_id=user.id,
                analysis_run_id=run.id,
            )
            await session.commit()

            # Verify persisted LLMRequest
            llm_res = await session.execute(
                select(LLMRequest).where(LLMRequest.analysis_run_id == run.id)
            )
            llm_entry = llm_res.scalar_one_or_none()
            assert llm_entry is not None
            assert llm_entry.provider == "deterministic"
            assert llm_entry.input_tokens > 0

            # Verify persisted UsageEvent
            usage_res = await session.execute(
                select(UsageEvent).where(UsageEvent.organization_id == org.id)
            )
            usage_events = usage_res.scalars().all()
            assert len(usage_events) >= 1
            assert any(u.event_type == "rag_generation" for u in usage_events)

            # Verify persisted AnalysisStep
            step_res = await session.execute(
                select(AnalysisStep).where(AnalysisStep.analysis_run_id == run.id)
            )
            step = step_res.scalar_one_or_none()
            assert step is not None
            assert step.step_type == "rag_generation"
            assert step.status == "completed"


class TestRAGAPIEndpoint:
    """Tests for REST API endpoint POST /api/v1/rag/answer."""

    @pytest.mark.asyncio
    async def test_api_answer_endpoint_success(self, test_env: dict[str, Any]) -> None:
        """Verify calling POST /api/v1/rag/answer with JWT token returns grounded answer schema."""
        client: AsyncClient = test_env["client"]
        async with test_env["session_factory"]() as session:
            _, org, token = await _seed_user_and_org(session)
            await _index_test_chunk(
                session,
                test_env,
                org.id,
                "In fiscal year 2025 net income totaled $42 million.",
                document_name="Income_Statement.pdf",
                page_number=12,
            )

        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "query": "What was net income in 2025?",
            "top_k": 5,
            "include_evidence": True,
        }

        resp = await client.post("/api/v1/rag/answer", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["grounded"] is True
        assert data["confidence"] >= 0.8
        assert "[E1]" in data["answer"]
        assert len(data["citations"]) == 1
        assert data["citations"][0]["evidence_id"] == "E1"
        assert len(data["evidence"]) >= 1
        assert "Income_Statement.pdf" in data["evidence"][0]["document_name"]
        assert data["diagnostics"]["llm_latency_ms"] >= 0.0

    @pytest.mark.asyncio
    async def test_api_unauthorized_request(self, test_env: dict[str, Any]) -> None:
        """Verify calling endpoint without auth returns 401 Unauthorized."""
        client: AsyncClient = test_env["client"]
        payload = {"query": "What is revenue?"}
        resp = await client.post("/api/v1/rag/answer", json=payload)
        assert resp.status_code == 401


class TestRAGPerformanceBenchmark:
    """Latency and execution profiling tests."""

    @pytest.mark.asyncio
    async def test_rag_latency_benchmark(self, test_env: dict[str, Any]) -> None:
        """Measure latency of each phase in full RAG pipeline."""
        async with test_env["session_factory"]() as session:
            _, org, _ = await _seed_user_and_org(session)
            await _index_test_chunk(
                session,
                test_env,
                org.id,
                "Total annual revenues reached $95 million in fiscal year 2025.",
            )

            rag_service: RAGService = test_env["rag_service"]

            t0 = time.perf_counter()
            result = await rag_service.answer(
                query="What was total annual revenue in 2025?",
                organization_id=org.id,
                session=session,
            )
            real_total_ms = (time.perf_counter() - t0) * 1000

            diag = result.diagnostics
            assert diag.total_ms > 0
            assert diag.retrieval_ms > 0
            assert diag.evidence_selection_ms >= 0
            assert diag.context_assembly_ms >= 0
            assert diag.llm_latency_ms >= 0
            assert real_total_ms < 3000.0  # Pipeline finishes well within budget

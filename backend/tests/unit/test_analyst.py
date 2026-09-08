"""Unit tests for Unified AI Analyst Orchestrator components."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.analyst.config import AnalystConfig
from app.analyst.conflicts import ConflictDetector
from app.analyst.exceptions import AnalystBudgetExceededError
from app.analyst.executor import ParallelAnalystExecutor
from app.analyst.merger import EvidenceMerger
from app.analyst.models import (
    AnalystRouteType,
    BranchType,
    ExecutionBranch,
    ExecutionPlan,
    UnifiedEvidence,
)
from app.analyst.planner import DeterministicAnalystPlanner
from app.analyst.router import AnalystQueryRouter
from app.rag.grounding import GroundingValidator
from app.rag.models import Evidence, GroundedAnswer, RAGAnswerResult
from app.sql_agent.models import (
    SQLAgentResult,
    SQLProvenance,
    SQLQueryResult,
    StructuredAnalysisResult,
)


class TestAnalystQueryRouter:
    """Test suite for multilingual intent classification and route selection."""

    def setup_method(self) -> None:
        self.router = AnalystQueryRouter()
        self.ds_id = uuid.uuid4()

    def test_structured_queries_route_to_sql(self) -> None:
        # English
        res_en = self.router.classify(
            "What was total revenue in Q4 2025?", datasource_id=self.ds_id
        )
        assert res_en.route == AnalystRouteType.SQL
        assert res_en.has_structured_intent is True

        # Arabic
        res_ar = self.router.classify(
            "ما هو إجمالي المبيعات للربع الأول؟", datasource_id=self.ds_id
        )
        assert res_ar.route == AnalystRouteType.SQL
        assert res_ar.has_structured_intent is True

        # Turkish
        res_tr = self.router.classify(
            "Dördüncü çeyrek toplam gelir nedir?", datasource_id=self.ds_id
        )
        assert res_tr.route == AnalystRouteType.SQL
        assert res_tr.has_structured_intent is True

    def test_unstructured_queries_route_to_rag(self) -> None:
        # English
        res_en = self.router.classify("What does the company policy say about remote work?")
        assert res_en.route == AnalystRouteType.RAG
        assert res_en.has_unstructured_intent is True

        # Arabic
        res_ar = self.router.classify("ما هي بنود عقد التوظيف وسياسة الإجازات؟")
        assert res_ar.route == AnalystRouteType.RAG

        # Turkish
        res_tr = self.router.classify("Şirket seyahat politikası hakkında ne söylüyor?")
        assert res_tr.route == AnalystRouteType.RAG

    def test_hybrid_queries_route_to_hybrid(self) -> None:
        # English
        q_en = "Revenue fell in Q4. What was the decline and what explanation does the report give?"
        res_en = self.router.classify(q_en, datasource_id=self.ds_id)
        assert res_en.route == AnalystRouteType.HYBRID
        assert res_en.has_structured_intent is True
        assert res_en.has_unstructured_intent is True

        # Arabic
        res_ar = self.router.classify(
            "لماذا انخفضت الإيرادات؟ وما الذي ذكره التقرير السنوي عن ذلك؟",
            datasource_id=self.ds_id,
        )
        assert res_ar.route == AnalystRouteType.HYBRID

        # Turkish
        res_tr = self.router.classify(
            "Gelir neden düştü ve yıllık rapor bu konuda ne söylüyor?",
            datasource_id=self.ds_id,
        )
        assert res_tr.route == AnalystRouteType.HYBRID

    def test_structured_query_without_datasource_falls_back_to_rag(self) -> None:
        res = self.router.classify("What was total revenue in Q4?")
        assert res.route == AnalystRouteType.RAG


class TestDeterministicAnalystPlanner:
    """Test suite for execution plan assembly, branch generation, and budgets."""

    def setup_method(self) -> None:
        self.config = AnalystConfig(max_branches=3, max_evidence=10)
        self.planner = DeterministicAnalystPlanner(config=self.config)
        self.ds_id = uuid.uuid4()

    def test_plan_sql_route(self) -> None:
        plan = self.planner.plan("What was total revenue in Q4?", datasource_id=self.ds_id)
        assert plan.route == AnalystRouteType.SQL
        assert len(plan.branches) == 1
        assert plan.branches[0].branch_type == BranchType.SQL
        assert plan.branches[0].datasource_id == self.ds_id

    def test_plan_rag_route(self) -> None:
        plan = self.planner.plan("Summarize executive leadership priorities in the annual report.")
        assert plan.route == AnalystRouteType.RAG
        assert len(plan.branches) == 1
        assert plan.branches[0].branch_type == BranchType.RAG

    def test_plan_hybrid_route(self) -> None:
        plan = self.planner.plan(
            "What was Q4 revenue and why did it fall according to the annual report?",
            datasource_id=self.ds_id,
        )
        assert plan.route == AnalystRouteType.HYBRID
        assert len(plan.branches) == 2
        types = {b.branch_type for b in plan.branches}
        assert types == {BranchType.SQL, BranchType.RAG}

    def test_budget_exceeded_raises_error(self) -> None:
        strict_config = AnalystConfig(max_branches=1)
        strict_planner = DeterministicAnalystPlanner(config=strict_config)
        with pytest.raises(AnalystBudgetExceededError):
            strict_planner.plan(
                "Why did revenue fall in Q4 and what does the annual report say?",
                datasource_id=self.ds_id,
            )


class TestEvidenceMerger:
    """Test suite for evidence consolidation, namespacing, and budget limits."""

    def test_merges_and_namespaces_evidence(self) -> None:
        merger = EvidenceMerger(max_evidence=5)

        # Mock SQL Result
        sql_res = SQLAgentResult(
            question="Revenue in Q4",
            generated_sql="SELECT sum(revenue) FROM sales",
            sql_hash="hash123",
            query_result=SQLQueryResult(
                columns=["quarter", "revenue"],
                rows=[{"quarter": "Q4", "revenue": "120000000.00"}],
                row_count=1,
            ),
            analysis=StructuredAnalysisResult(
                summary="Total revenue: $120,000,000.00.",
                metrics={"total_revenue": 120000000.0},
            ),
            provenance=SQLProvenance(
                sql_hash="hash123",
                normalized_sql="SELECT sum(revenue) FROM sales",
                datasource_id=str(uuid.uuid4()),
                tables_used=["sales"],
                columns_used=["quarter", "revenue"],
                row_count=1,
                duration_ms=10.0,
            ),
        )

        # Mock RAG Result
        rag_res = RAGAnswerResult(
            query="Explanation from report",
            answer=GroundedAnswer(
                answer="Enterprise demand fell in Q4 [E1].",
                evidence_ids=["E1"],
                grounded=True,
                confidence=0.9,
                system_grounding_confidence=0.9,
            ),
            evidence=[
                Evidence(
                    evidence_id="E1",
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    organization_id=uuid.uuid4(),
                    rank=1,
                    rerank_score=0.95,
                    text="Enterprise demand decreased across North America in Q4.",
                    page_number=12,
                    document_name="Annual_Report_2025.pdf",
                )
            ],
        )

        unified = merger.merge(sql_results=[sql_res], rag_results=[rag_res])
        assert len(unified) >= 2

        # Check namespaces
        sql_items = [u for u in unified if u.evidence_id.startswith("S")]
        rag_items = [u for u in unified if u.evidence_id.startswith("R")]

        assert len(sql_items) >= 1
        assert len(rag_items) == 1
        assert sql_items[0].is_calculated is True
        assert rag_items[0].is_calculated is False
        assert "120,000,000.00" in sql_items[0].text
        assert "North America" in rag_items[0].text


class TestConflictDetector:
    """Test suite for detecting quantitative discrepancies between sources."""

    def setup_method(self) -> None:
        self.detector = ConflictDetector()

    def test_detects_revenue_discrepancy(self) -> None:
        evidence = [
            UnifiedEvidence(
                evidence_id="S1",
                source_type="sql",
                title="Sales Table",
                text="Computed total revenue: 120M.",
                is_calculated=True,
                metadata={"metrics": {"total_revenue": 120000000.0}},
            ),
            UnifiedEvidence(
                evidence_id="R1",
                source_type="document",
                title="Annual Report",
                text="The annual report states annual revenue was 100M.",
                is_calculated=False,
            ),
        ]

        conflicts = self.detector.detect(evidence)
        assert len(conflicts) == 1
        c = conflicts[0]
        assert "120,000,000.00" in str(c.value_a)
        assert "100,000,000.00" in str(c.value_b)
        assert "Discrepancy" in c.description

    def test_no_conflict_when_values_match(self) -> None:
        evidence = [
            UnifiedEvidence(
                evidence_id="S1",
                source_type="sql",
                title="Sales Table",
                text="Total revenue: 100M.",
                is_calculated=True,
                metadata={"metrics": {"revenue": 100000000.0}},
            ),
            UnifiedEvidence(
                evidence_id="R1",
                source_type="document",
                title="Report",
                text="Revenue stood at $100M.",
                is_calculated=False,
            ),
        ]
        conflicts = self.detector.detect(evidence)
        assert len(conflicts) == 0


class TestGroundingValidatorExtension:
    """Verify GroundingValidator accepts [S#] and [R#] citation markers."""

    def test_accepts_s_and_r_citations(self) -> None:
        validator = GroundingValidator()
        available = [
            Evidence(
                evidence_id="S1",
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                organization_id=uuid.uuid4(),
                rank=1,
                rerank_score=0.9,
                text="Revenue reached 120M.",
            ),
            Evidence(
                evidence_id="R1",
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                organization_id=uuid.uuid4(),
                rank=2,
                rerank_score=0.85,
                text="Management noted strong demand.",
            ),
        ]

        raw_answer = "Revenue reached $120M [S1]. Management noted strong demand [R1] [S99]."
        res = validator.validate_and_repair(
            raw_answer=raw_answer,
            claimed_evidence_ids=["S1", "R1"],
            claimed_grounded=True,
            claimed_confidence=0.9,
            available_evidence=available,
        )

        assert res.grounded is True
        assert "S1" in res.evidence_ids
        assert "R1" in res.evidence_ids
        # Phantom citation [S99] stripped
        assert "[S99]" not in res.answer


class TestParallelAnalystExecutor:
    """Test suite for concurrent branch execution and timeout/degradation behavior."""

    @pytest.mark.asyncio
    async def test_partial_branch_failure_handling(self) -> None:
        sql_mock = MagicMock()
        sql_mock.execute_question = AsyncMock(side_effect=RuntimeError("Database connection lost"))

        rag_mock = MagicMock()
        rag_mock.answer = AsyncMock(
            return_value=RAGAnswerResult(
                query="test",
                answer=GroundedAnswer(
                    answer="Document answer [R1]",
                    evidence_ids=["R1"],
                    grounded=True,
                    confidence=0.8,
                    system_grounding_confidence=0.8,
                ),
                evidence=[],
            )
        )

        executor = ParallelAnalystExecutor(
            sql_service=sql_mock,
            rag_service=rag_mock,
            config=AnalystConfig(total_timeout_seconds=5.0),
        )

        plan = ExecutionPlan(
            plan_id=uuid.uuid4(),
            original_query="hybrid test",
            route=AnalystRouteType.HYBRID,
            confidence=0.9,
            branches=[
                ExecutionBranch(
                    branch_id="b_sql_1",
                    branch_type=BranchType.SQL,
                    query="revenue query",
                    datasource_id=uuid.uuid4(),
                ),
                ExecutionBranch(
                    branch_id="b_rag_1",
                    branch_type=BranchType.RAG,
                    query="report query",
                ),
            ],
        )

        results = await executor.execute_plan(
            plan=plan,
            organization_id=uuid.uuid4(),
            session=AsyncMock(),
        )

        assert len(results) == 2
        sql_res = next(r for r in results if r.branch_type == BranchType.SQL)
        rag_res = next(r for r in results if r.branch_type == BranchType.RAG)

        assert sql_res.success is False
        assert "Database connection lost" in (sql_res.error or "")
        assert rag_res.success is True

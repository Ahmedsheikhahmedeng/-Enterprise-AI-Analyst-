"""RAG orchestration service coordinating query planning, retrieval, evidence, and generation."""

import logging
import time
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisStep
from app.models.usage import LLMRequest, UsageEvent
from app.query.service import QueryUnderstandingService
from app.rag.config import RAGConfig, get_rag_config
from app.rag.context import ContextAssembler
from app.rag.evidence import EvidenceSelector
from app.rag.grounding import GroundingValidator
from app.rag.models import (
    GroundedAnswer,
    RAGAnswerResult,
    RAGDiagnostics,
)
from app.rag.prompts import PromptBuilder
from app.rag.providers.base import RAGLLMProvider
from app.rag.providers.factory import RAGProviderFactory
from app.retrieval.hybrid.service import HybridRetrievalService

logger = logging.getLogger(__name__)


class RAGService:
    """Core RAG orchestrator decoupled from underlying storage engines and LLM SDKs."""

    def __init__(
        self,
        hybrid_retrieval_service: HybridRetrievalService,
        query_understanding_service: QueryUnderstandingService | None = None,
        provider: RAGLLMProvider | None = None,
        config: RAGConfig | None = None,
    ) -> None:
        self.config = config or get_rag_config()
        self.hybrid_retrieval = hybrid_retrieval_service
        self.query_understanding = query_understanding_service
        self.provider = provider or RAGProviderFactory.create(self.config)
        self.evidence_selector = EvidenceSelector()
        self.context_assembler = ContextAssembler()
        self.prompt_builder = PromptBuilder(prompt_version=self.config.prompt_version)
        self.grounding_validator = GroundingValidator()

    async def answer(
        self,
        query: str,
        organization_id: UUID,
        *,
        session: AsyncSession,
        top_k: int | None = None,
        user_id: UUID | None = None,
        conversation_id: UUID | None = None,
        analysis_run_id: UUID | None = None,
        enable_query_understanding: bool = True,
    ) -> RAGAnswerResult:
        """Execute full evidence-grounded RAG flow from query to verified answer."""
        t_total_start = time.perf_counter()
        diagnostics = RAGDiagnostics(
            model=self.provider.model_name,
            provider=self.provider.provider_name,
            prompt_version=self.config.prompt_version,
        )
        eff_top_k = top_k or self.config.evidence_top_k

        # 1. Query Understanding & Planning
        t_under_start = time.perf_counter()
        search_plan = None
        if self.query_understanding and enable_query_understanding:
            try:
                search_plan = await self.query_understanding.analyze_and_plan(
                    query, organization_id=organization_id
                )
            except Exception as exc:
                logger.warning("Query understanding error during RAG (%s); using raw query", exc)
        diagnostics.understanding_ms = (time.perf_counter() - t_under_start) * 1000

        # 2. Hybrid Retrieval + RRF + Cross-Encoder Reranking
        t_ret_start = time.perf_counter()
        # Retrieve candidate pool (3x top_k to allow diverse evidence selection)
        candidates_to_fetch = max(15, eff_top_k * 3)
        hybrid_res = await self.hybrid_retrieval.search(
            query=query,
            organization_id=organization_id,
            session=session,
            top_k=candidates_to_fetch,
            rerank=True,
            include_parent=True,
            enable_query_understanding=enable_query_understanding,
        )
        retrieved_chunks = hybrid_res.chunks
        retrieval_elapsed = (time.perf_counter() - t_ret_start) * 1000
        diagnostics.retrieval_ms = retrieval_elapsed
        diagnostics.retrieved_count = len(retrieved_chunks)
        diagnostics.reranked_count = len(retrieved_chunks)

        # 3. Fast Exit: No Evidence Available
        if not retrieved_chunks:
            diagnostics.total_ms = (time.perf_counter() - t_total_start) * 1000
            no_evidence_answer = GroundedAnswer(
                answer=(
                    "لم أجد معلومات كافية في المستندات المتاحة للإجابة عن هذا السؤال."
                    if any(c in query for c in "لماذا ما سبب أثر تراجع")
                    else "I could not find sufficient information in the available documents."
                ),
                evidence_ids=[],
                grounded=False,
                confidence=0.0,
                system_grounding_confidence=0.0,
                model_confidence=None,
                language=self.config.response_language,
                model=self.provider.model_name,
                prompt_version=self.config.prompt_version,
            )
            return RAGAnswerResult(
                query=query,
                answer=no_evidence_answer,
                evidence=[],
                search_plan=search_plan,
                diagnostics=diagnostics,
            )

        # 4. Evidence Selection & Light Diversity Filtering
        t_ev_start = time.perf_counter()
        evidence_list = self.evidence_selector.select_evidence(
            chunks=retrieved_chunks,
            organization_id=organization_id,
            top_k=eff_top_k,
            min_evidence_score=self.config.min_evidence_score,
        )
        diagnostics.evidence_selection_ms = (time.perf_counter() - t_ev_start) * 1000
        diagnostics.evidence_count = len(evidence_list)

        if not evidence_list:
            diagnostics.total_ms = (time.perf_counter() - t_total_start) * 1000
            empty_evidence_answer = GroundedAnswer(
                answer=(
                    "The available documents do not contain high-confidence "
                    "information for this query."
                ),
                evidence_ids=[],
                grounded=False,
                confidence=0.1,
                system_grounding_confidence=0.1,
                model_confidence=None,
                language=self.config.response_language,
                model=self.provider.model_name,
                prompt_version=self.config.prompt_version,
            )
            return RAGAnswerResult(
                query=query,
                answer=empty_evidence_answer,
                evidence=[],
                search_plan=search_plan,
                diagnostics=diagnostics,
            )

        # 5. Context Assembly within Token Budget
        t_ctx_start = time.perf_counter()
        context_text, included_evidence, context_tokens = self.context_assembler.assemble(
            evidence_list=evidence_list,
            max_context_tokens=self.config.max_context_tokens,
        )
        diagnostics.context_assembly_ms = (time.perf_counter() - t_ctx_start) * 1000
        diagnostics.context_tokens = context_tokens

        # 6. Prompt Construction with Injection Boundaries
        system_prompt = self.prompt_builder.build_system_prompt(
            response_language=self.config.response_language
        )
        user_prompt = self.prompt_builder.build_user_prompt(query=query, context_text=context_text)

        # 7. LLM Answer Generation
        t_llm_start = time.perf_counter()
        provider_resp = await self.provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=self.config.max_output_tokens,
            temperature=self.config.temperature,
        )
        diagnostics.llm_latency_ms = (time.perf_counter() - t_llm_start) * 1000
        diagnostics.input_tokens = provider_resp.input_tokens
        diagnostics.output_tokens = provider_resp.output_tokens

        # Estimate simple cost based on typical gpt-4o-mini rates ($0.15/1M in, $0.60/1M out)
        est_cost = (provider_resp.input_tokens * 0.00000015) + (
            provider_resp.output_tokens * 0.00000060
        )
        diagnostics.cost_usd = round(min(est_cost, self.config.max_cost_per_request), 6)

        # 8. Grounding & Citation Validation
        grounded_answer = self.grounding_validator.validate_and_repair(
            raw_answer=provider_resp.answer,
            claimed_evidence_ids=provider_resp.evidence_ids,
            claimed_grounded=provider_resp.grounded,
            claimed_confidence=provider_resp.confidence,
            available_evidence=included_evidence,
        )
        grounded_answer.model = self.provider.model_name
        grounded_answer.prompt_version = self.config.prompt_version

        diagnostics.total_ms = (time.perf_counter() - t_total_start) * 1000

        # 9. Persistence & Observability
        from app.observability.context import get_current_context
        from app.observability.instrumentation.llm import get_llm_instrumentation
        from app.observability.instrumentation.rag import get_rag_instrumentation

        obs_ctx = get_current_context()
        trace_id_val = obs_ctx.trace_id if obs_ctx else None
        span_id_val = obs_ctx.span_id if obs_ctx else None
        request_id_val = obs_ctx.request_id if obs_ctx else None

        # Telemetry recording
        rag_lang = "ar" if any("\u0600" <= c <= "\u06ff" for c in query) else "en"
        get_rag_instrumentation().record_rag_request(
            duration_ms=diagnostics.total_ms,
            status="ok",
            language=rag_lang,
            is_empty_context=(len(included_evidence) == 0),
        )
        get_rag_instrumentation().record_retrieval(
            duration_ms=diagnostics.retrieval_ms,
            final_returned=len(included_evidence),
        )
        get_llm_instrumentation().record_llm_call(
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            operation="rag_generation",
            status="ok",
            duration_ms=diagnostics.llm_latency_ms,
            input_tokens=provider_resp.input_tokens,
            output_tokens=provider_resp.output_tokens,
            cost_usd=float(diagnostics.cost_usd),
        )

        if session is not None:
            try:
                # Persist LLMRequest ledger
                llm_entry = LLMRequest(
                    organization_id=organization_id,
                    user_id=user_id,
                    analysis_run_id=analysis_run_id,
                    provider=self.provider.provider_name,
                    model=self.provider.model_name,
                    input_tokens=provider_resp.input_tokens,
                    output_tokens=provider_resp.output_tokens,
                    total_tokens=provider_resp.input_tokens + provider_resp.output_tokens,
                    estimated_cost=Decimal(str(diagnostics.cost_usd)),
                    latency_ms=int(diagnostics.llm_latency_ms),
                    status="success",
                    trace_id=trace_id_val,
                    span_id=span_id_val,
                    request_id=request_id_val,
                )
                session.add(llm_entry)

                # Persist UsageEvent
                usage_event = UsageEvent(
                    organization_id=organization_id,
                    user_id=user_id,
                    event_type="rag_generation",
                    quantity=provider_resp.output_tokens,
                    metadata_={
                        "query_length": len(query),
                        "evidence_count": len(included_evidence),
                        "model": self.provider.model_name,
                        "grounded": grounded_answer.grounded,
                    },
                )
                session.add(usage_event)

                # If analysis_run_id provided, record analysis step
                if analysis_run_id is not None:
                    step = AnalysisStep(
                        analysis_run_id=analysis_run_id,
                        step_type="rag_generation",
                        step_order=1,
                        status="completed",
                        input_payload={"query": query, "evidence_count": len(included_evidence)},
                        output_payload={
                            "grounded": grounded_answer.grounded,
                            "citations": [c.evidence_id for c in grounded_answer.citations],
                            "confidence": grounded_answer.confidence,
                        },
                    )
                    session.add(step)

                await session.flush()
            except Exception as exc:
                logger.warning("Failed to persist RAG telemetry to database (%s)", exc)

        return RAGAnswerResult(
            query=query,
            answer=grounded_answer,
            evidence=included_evidence,
            search_plan=search_plan,
            diagnostics=diagnostics,
        )

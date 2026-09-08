"""Orchestration service for query understanding, safety, and search planning."""

import asyncio
import hashlib
import logging
import time
import uuid

from app.query.config import QueryUnderstandingConfig, get_query_understanding_config
from app.query.deduplication import QueryDeduplicator
from app.query.entities import EntityExtractor
from app.query.models import (
    QueryAnalysis,
    QueryDiagnostics,
    QueryRetrievalBudget,
    SearchPlan,
)
from app.query.providers.base import QueryUnderstandingProvider
from app.query.providers.factory import QueryUnderstandingProviderFactory
from app.query.safety import QuerySafetyValidator

logger = logging.getLogger(__name__)


class QueryUnderstandingService:
    """Core domain service for analyzing user queries and building SearchPlans."""

    def __init__(
        self,
        provider: QueryUnderstandingProvider | None = None,
        config: QueryUnderstandingConfig | None = None,
    ) -> None:
        self.config = config or get_query_understanding_config()
        self.provider = provider or QueryUnderstandingProviderFactory.create(self.config)
        self.safety_validator = QuerySafetyValidator()
        self.deduplicator = QueryDeduplicator()
        self.entity_extractor = EntityExtractor()
        # In-memory tenant-safe cache: (tenant_id, query_hash) -> SearchPlan
        self._cache: dict[tuple[uuid.UUID, str], SearchPlan] = {}

    def _hash_query(self, query: str) -> str:
        return hashlib.sha256(query.encode("utf-8")).hexdigest()

    async def analyze_and_plan(
        self,
        query: str,
        *,
        organization_id: uuid.UUID | None = None,
        enable_rewrite: bool | None = None,
        enable_expansion: bool | None = None,
        enable_decomposition: bool | None = None,
        max_alternatives: int | None = None,
        max_subqueries: int | None = None,
        previous_user_query: str | None = None,
        previous_assistant_context: str | None = None,
    ) -> SearchPlan:
        """Analyze query, extract entities, apply rewrites, and construct executable SearchPlan."""
        t0 = time.perf_counter()
        diagnostics = QueryDiagnostics(
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            prompt_version=self.config.prompt_version,
        )

        # 1. Safety & length validation
        sanitized_query = self.safety_validator.validate_and_sanitize(query)

        # 2. Check tenant-safe cache
        cache_key = None
        if organization_id is not None:
            cache_key = (organization_id, self._hash_query(sanitized_query))
            if cache_key in self._cache:
                cached_plan = self._cache[cache_key]
                logger.debug("Cache hit for query understanding plan (hash=%s)", cache_key[1][:8])
                return cached_plan

        # Feature flags resolution
        do_rewrite = enable_rewrite if enable_rewrite is not None else self.config.rewrite_enabled
        do_expansion = (
            enable_expansion if enable_expansion is not None else self.config.expansion_enabled
        )
        do_decomposition = (
            enable_decomposition
            if enable_decomposition is not None
            else self.config.decomposition_enabled
        )
        eff_max_alts = (
            max_alternatives
            if max_alternatives is not None
            else self.config.max_alternative_queries
        )
        eff_max_subs = max_subqueries if max_subqueries is not None else self.config.max_subqueries

        # 3. Provider invocation with latency budget
        t_analysis_start = time.perf_counter()
        try:
            analysis: QueryAnalysis = await asyncio.wait_for(
                self.provider.analyze(
                    sanitized_query,
                    enable_rewrite=do_rewrite,
                    enable_expansion=do_expansion,
                    enable_decomposition=do_decomposition,
                    max_alternatives=eff_max_alts,
                    max_subqueries=eff_max_subs,
                ),
                timeout=self.config.timeout_seconds,
            )
        except TimeoutError:
            diagnostics.is_degraded = True
            diagnostics.degradation_reason = (
                f"Query understanding timed out after {self.config.timeout_seconds}s; fallback"
            )
            logger.warning(diagnostics.degradation_reason)
            analysis = QueryAnalysis(
                original_query=query,
                normalized_query=sanitized_query,
                language="unknown",
                confidence=0.5,
            )
        except Exception as exc:
            diagnostics.is_degraded = True
            diagnostics.degradation_reason = (
                f"Query understanding failed ({exc}); fallback to raw query"
            )
            logger.warning(diagnostics.degradation_reason)
            analysis = QueryAnalysis(
                original_query=query,
                normalized_query=sanitized_query,
                language="unknown",
                confidence=0.5,
            )

        diagnostics.total_understanding_ms = round(
            (time.perf_counter() - t_analysis_start) * 1000.0, 3
        )

        # 4. Complexity & Confidence Control
        # If confidence is below threshold, prefer original normalized query
        use_rewrite = (
            analysis.rewritten_query is not None
            and analysis.confidence >= self.config.confidence_threshold
        )
        resolved_primary = analysis.rewritten_query if use_rewrite else analysis.normalized_query
        primary_query: str = resolved_primary or analysis.normalized_query or query

        # 5. Build hard filters vs soft hints
        hard_filters, soft_filters = self.entity_extractor.build_filters(analysis.entities)

        # 6. Deduplicate alternative queries and sub-queries
        all_raw_alts = analysis.expanded_queries
        deduped_alts = self.deduplicator.deduplicate(
            [q for q in all_raw_alts if q.lower() != primary_query.lower()],
            max_queries=eff_max_alts,
        )

        all_raw_subs = analysis.sub_queries
        deduped_subs = self.deduplicator.deduplicate(
            [q for q in all_raw_subs if q.lower() != primary_query.lower()],
            max_queries=eff_max_subs,
        )

        # Enforce hard ceiling on total queries
        total_queries_planned = 1 + len(deduped_alts) + len(deduped_subs)
        if total_queries_planned > self.config.max_total_queries:
            # Scale down
            excess = total_queries_planned - self.config.max_total_queries
            if len(deduped_alts) >= excess:
                deduped_alts = deduped_alts[:-excess]
            else:
                remaining_excess = excess - len(deduped_alts)
                deduped_alts = []
                deduped_subs = deduped_subs[:-remaining_excess]

        diagnostics.total_understanding_ms = (time.perf_counter() - t0) * 1000

        budget = QueryRetrievalBudget(
            max_queries=self.config.max_total_queries,
            max_candidates_per_query=50,
            max_total_candidates=150,
            timeout_seconds=self.config.total_pipeline_timeout_seconds,
        )

        plan = SearchPlan(
            original_query=query,
            primary_query=primary_query,
            alternative_queries=deduped_alts,
            sub_queries=deduped_subs,
            language=analysis.language,
            detected_languages=analysis.detected_languages,
            intent=analysis.intent,
            entities=analysis.entities,
            hard_filters=hard_filters,
            soft_filters=soft_filters,
            retrieval_budget=budget,
            confidence=analysis.confidence,
            diagnostics=diagnostics,
        )

        # Store in tenant cache (keep cache small, max 500 entries)
        if cache_key is not None:
            if len(self._cache) > 500:
                self._cache.clear()
            self._cache[cache_key] = plan

        return plan

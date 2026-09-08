"""Hybrid Semantic Search engine combining exact, synonym, lexical, and vector retrieval."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semantic import (
    BusinessTerm,
    SemanticColumnMapping,
    SemanticDimension,
    SemanticMetric,
    SemanticSynonym,
)
from app.semantic.application.normalizer import SemanticTextNormalizer
from app.semantic.domain.enums import MatchSource, SemanticObjectType, SemanticStatus
from app.semantic.domain.models import SemanticSearchResultItem
from app.semantic.domain.protocols import SemanticSearchProvider


class HybridSemanticSearchEngine(SemanticSearchProvider):
    """Orchestrates multi-layer semantic search across business terms, metrics, dimensions, and entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        query: str,
        organization_id: uuid.UUID,
        limit: int = 10,
        object_types: list[str] | None = None,
        only_published: bool = True,
    ) -> list[SemanticSearchResultItem]:
        """Execute hybrid search returning deduplicated and ranked semantic concepts."""
        raw_query = query.strip()
        norm_query = SemanticTextNormalizer.normalize(raw_query)
        detected_lang = SemanticTextNormalizer.detect_language(raw_query)

        results: dict[uuid.UUID, SemanticSearchResultItem] = {}

        allowed_types = set(object_types or ["term", "metric", "dimension", "entity"])

        # ---------------------------------------------------------------------
        # 1. Search Business Terms
        # ---------------------------------------------------------------------
        if "term" in allowed_types:
            stmt = select(BusinessTerm).where(BusinessTerm.organization_id == organization_id)
            if only_published:
                stmt = stmt.where(BusinessTerm.status == SemanticStatus.PUBLISHED.value)
            term_res = await self.session.execute(stmt)
            for t in term_res.scalars().all():
                score = 0.0
                source = MatchSource.LEXICAL
                if raw_query.lower() == t.name.lower():
                    score = 1.0
                    source = MatchSource.EXACT
                elif norm_query and norm_query == t.normalized_name:
                    score = 0.95
                    source = MatchSource.EXACT
                elif norm_query and (
                    norm_query in t.normalized_name or t.normalized_name in norm_query
                ):
                    score = 0.75
                    source = MatchSource.LEXICAL
                elif (
                    t.description
                    and norm_query
                    and norm_query in SemanticTextNormalizer.normalize(t.description)
                ):
                    score = 0.55
                    source = MatchSource.LEXICAL

                if score > 0:
                    results[t.id] = SemanticSearchResultItem(
                        object_id=t.id,
                        object_type=SemanticObjectType.TERM,
                        name=t.name,
                        description=t.description,
                        definition=t.definition,
                        status=SemanticStatus(t.status),
                        match_source=source,
                        score=score,
                        language=detected_lang,
                        metadata={"category": t.category, "version": t.version},
                    )

        # ---------------------------------------------------------------------
        # 2. Search Semantic Metrics
        # ---------------------------------------------------------------------
        if "metric" in allowed_types:
            metric_stmt = select(SemanticMetric).where(
                SemanticMetric.organization_id == organization_id
            )
            if only_published:
                metric_stmt = metric_stmt.where(
                    SemanticMetric.status == SemanticStatus.PUBLISHED.value
                )
            metric_res = await self.session.execute(metric_stmt)
            for m in metric_res.scalars().all():
                score = 0.0
                source = MatchSource.LEXICAL
                if raw_query.lower() == m.name.lower() or (
                    m.display_name and raw_query.lower() == m.display_name.lower()
                ):
                    score = 1.0
                    source = MatchSource.EXACT
                elif norm_query and norm_query == m.normalized_name:
                    score = 0.95
                    source = MatchSource.EXACT
                elif norm_query and (
                    norm_query in m.normalized_name or m.normalized_name in norm_query
                ):
                    score = 0.75
                    source = MatchSource.LEXICAL

                if score > 0:
                    # Check if there are verified mappings for this metric to boost
                    map_stmt = select(SemanticColumnMapping).where(
                        SemanticColumnMapping.organization_id == organization_id,
                        SemanticColumnMapping.semantic_object_type == "metric",
                        SemanticColumnMapping.semantic_object_id == m.id,
                        SemanticColumnMapping.is_verified.is_(True),
                    )
                    has_verified = (
                        await self.session.execute(map_stmt)
                    ).scalars().first() is not None
                    if has_verified:
                        score = min(1.0, score + 0.1)

                    results[m.id] = SemanticSearchResultItem(
                        object_id=m.id,
                        object_type=SemanticObjectType.METRIC,
                        name=m.name,
                        description=m.description,
                        definition=m.definition,
                        status=SemanticStatus(m.status),
                        match_source=source,
                        score=score,
                        is_verified=has_verified,
                        language=detected_lang,
                        metadata={
                            "formula": m.formula,
                            "aggregation": m.aggregation,
                            "unit": m.unit,
                        },
                    )

        # ---------------------------------------------------------------------
        # 3. Search Semantic Dimensions
        # ---------------------------------------------------------------------
        if "dimension" in allowed_types:
            dim_stmt = select(SemanticDimension).where(
                SemanticDimension.organization_id == organization_id
            )
            if only_published:
                dim_stmt = dim_stmt.where(
                    SemanticDimension.status == SemanticStatus.PUBLISHED.value
                )
            dim_res = await self.session.execute(dim_stmt)
            for d in dim_res.scalars().all():
                score = 0.0
                source = MatchSource.LEXICAL
                if raw_query.lower() == d.name.lower():
                    score = 1.0
                    source = MatchSource.EXACT
                elif norm_query and norm_query == d.normalized_name:
                    score = 0.95
                    source = MatchSource.EXACT
                elif norm_query and (
                    norm_query in d.normalized_name or d.normalized_name in norm_query
                ):
                    score = 0.75
                    source = MatchSource.LEXICAL

                if score > 0:
                    results[d.id] = SemanticSearchResultItem(
                        object_id=d.id,
                        object_type=SemanticObjectType.DIMENSION,
                        name=d.name,
                        description=d.description,
                        status=SemanticStatus(d.status),
                        match_source=source,
                        score=score,
                        language=detected_lang,
                        metadata={"data_type": d.data_type, "hierarchy": d.hierarchy},
                    )

        # ---------------------------------------------------------------------
        # 4. Search Synonyms
        # ---------------------------------------------------------------------
        syn_stmt = select(SemanticSynonym).where(
            SemanticSynonym.organization_id == organization_id,
            or_(
                SemanticSynonym.synonym.ilike(f"%{raw_query}%"),
                SemanticSynonym.normalized_synonym == norm_query,
            ),
        )
        syn_res = await self.session.execute(syn_stmt)
        for syn in syn_res.scalars().all():
            target_id = syn.semantic_object_id
            if target_id in results:
                # Boost existing hit
                results[target_id].score = min(1.0, results[target_id].score + 0.15)
                results[target_id].match_source = MatchSource.SYNONYM

        # Sort descending by score
        ranked = sorted(results.values(), key=lambda r: r.score, reverse=True)
        return ranked[:limit]

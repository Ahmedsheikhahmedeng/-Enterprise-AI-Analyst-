"""Semantic Query Planner resolving natural language questions into grounded semantic query blueprints."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.dataset import Dataset
from app.models.semantic import (
    SemanticColumnMapping,
    SemanticDimension,
    SemanticMetric,
)
from app.semantic.application.metric_compiler import MetricCompiler
from app.semantic.domain.enums import SemanticObjectType, SemanticStatus
from app.semantic.domain.models import (
    ColumnMappingItem,
    ResolvedDimension,
    ResolvedMetric,
    SemanticQueryPlan,
)
from app.semantic.infrastructure.search import HybridSemanticSearchEngine


class SemanticQueryPlanner:
    """Transforms natural language questions into structured, verified semantic query execution plans."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.search_engine = HybridSemanticSearchEngine(session)

    async def plan_query(
        self,
        question: str,
        organization_id: uuid.UUID,
        target_dataset_id: uuid.UUID | None = None,
    ) -> SemanticQueryPlan:
        """Resolve question terms to published metrics, dimensions, and compiled SQL hints."""
        # 1. Hybrid search for relevant metrics and dimensions
        search_hits = await self.search_engine.search(
            query=question,
            organization_id=organization_id,
            limit=5,
            object_types=["metric", "dimension", "term"],
            only_published=True,
        )

        resolved_metrics: list[ResolvedMetric] = []
        resolved_dimensions: list[ResolvedDimension] = []
        resolved_entities: list[str] = []
        dataset_id = target_dataset_id
        dataset_version_id = None
        sql_hint: str | None = None
        is_authoritative = False
        provenance: dict[str, Any] = {"search_hits": len(search_hits), "mappings": []}

        # 2. Resolve Metrics
        for hit in search_hits:
            if hit.object_type == SemanticObjectType.METRIC:
                metric_stmt = select(SemanticMetric).where(
                    SemanticMetric.id == hit.object_id,
                    SemanticMetric.organization_id == organization_id,
                    SemanticMetric.status == SemanticStatus.PUBLISHED.value,
                )
                m = (await self.session.execute(metric_stmt)).scalars().first()
                if m:
                    # Fetch column mappings
                    map_stmt = (
                        select(SemanticColumnMapping)
                        .where(
                            SemanticColumnMapping.organization_id == organization_id,
                            SemanticColumnMapping.semantic_object_type == "metric",
                            SemanticColumnMapping.semantic_object_id == m.id,
                        )
                        .options(selectinload(SemanticColumnMapping.column))
                    )
                    map_records = list((await self.session.execute(map_stmt)).scalars().all())

                    col_items: list[ColumnMappingItem] = []
                    has_verified_mapping = False
                    col_dict: dict[str, str] = {}

                    for cm in map_records:
                        col_name = cm.column.name if cm.column else "val"
                        col_items.append(
                            ColumnMappingItem(
                                mapping_id=cm.id,
                                dataset_id=cm.dataset_id,
                                column_id=cm.column_id,
                                column_name=col_name,
                                mapping_type=cm.mapping_type,
                                confidence=cm.confidence,
                                is_verified=cm.is_verified,
                            )
                        )
                        col_dict[col_name] = col_name
                        if cm.is_verified:
                            has_verified_mapping = True
                        if dataset_id is None:
                            dataset_id = cm.dataset_id

                    resolved_metrics.append(
                        ResolvedMetric(
                            metric_id=m.id,
                            name=m.name,
                            display_name=m.display_name,
                            formula=m.formula,
                            aggregation=m.aggregation,
                            dataset_id=m.dataset_id or dataset_id,
                            confidence=hit.score,
                            is_verified=has_verified_mapping,
                            status=SemanticStatus(m.status),
                            column_mappings=col_items,
                        )
                    )

                    # Build safe SQL hint if dataset exists
                    if dataset_id and col_dict:
                        ds_stmt = select(Dataset).where(
                            Dataset.id == dataset_id,
                            Dataset.organization_id == organization_id,
                        )
                        ds = (await self.session.execute(ds_stmt)).scalars().first()
                        if ds:
                            dataset_version_id = ds.current_version
                            sql_hint = MetricCompiler.compile_metric(
                                metric_name=m.normalized_name.replace(" ", "_"),
                                formula=m.formula,
                                aggregation=m.aggregation,
                                table_name=ds.name,
                                column_mapping=col_dict,
                                filters=m.filters,
                            )

            elif hit.object_type == SemanticObjectType.DIMENSION:
                dim_stmt = (
                    select(SemanticDimension)
                    .where(
                        SemanticDimension.id == hit.object_id,
                        SemanticDimension.organization_id == organization_id,
                        SemanticDimension.status == SemanticStatus.PUBLISHED.value,
                    )
                    .options(selectinload(SemanticDimension.column))
                )
                d = (await self.session.execute(dim_stmt)).scalars().first()
                if d and d.column:
                    resolved_dimensions.append(
                        ResolvedDimension(
                            dimension_id=d.id,
                            name=d.name,
                            dataset_id=d.dataset_id,
                            column_id=d.column_id,
                            column_name=d.column.name,
                            data_type=d.data_type,
                            confidence=hit.score,
                            status=SemanticStatus(d.status),
                        )
                    )

        # Plan is authoritative only if we have at least one verified published metric
        if any(rm.is_verified for rm in resolved_metrics):
            is_authoritative = True

        provenance["resolved_metrics_count"] = len(resolved_metrics)
        provenance["resolved_dimensions_count"] = len(resolved_dimensions)

        return SemanticQueryPlan(
            question=question,
            resolved_metrics=resolved_metrics,
            resolved_dimensions=resolved_dimensions,
            resolved_entities=resolved_entities,
            dataset_id=dataset_id,
            dataset_version_id=dataset_version_id,
            sql_hint=sql_hint,
            filters=[],
            is_authoritative=is_authoritative,
            provenance=provenance,
        )

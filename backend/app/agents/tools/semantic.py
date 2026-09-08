"""Typed Agent Tools exposing Semantic Catalog and Semantic Layer capabilities."""

import time
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agents.context import AgentExecutionContext
from app.agents.exceptions import ToolInputValidationError
from app.agents.schemas import ToolRiskLevel
from app.agents.tools.base import ToolOutput
from app.agents.tools.schemas import (
    SemanticGetEntityInput,
    SemanticGetQueryPlanInput,
    SemanticGetRelationshipsInput,
    SemanticGetTermInput,
    SemanticResolveDimensionInput,
    SemanticResolveMetricInput,
    SemanticSearchInput,
)
from app.models.semantic import (
    BusinessTerm,
    SemanticColumnMapping,
    SemanticDimension,
    SemanticEntity,
    SemanticMetric,
    SemanticRelationship,
)
from app.rbac.catalog import PERM_SEMANTIC_READ
from app.semantic.application.normalizer import SemanticTextNormalizer
from app.semantic.application.query_planner import SemanticQueryPlanner
from app.semantic.domain.enums import SemanticStatus
from app.semantic.infrastructure.search import HybridSemanticSearchEngine


class SemanticSearchTool:
    """Tool performing hybrid semantic discovery over business concepts."""

    name: str = "semantic.search"
    version: str = "v1.0"
    description: str = (
        "Searches business terms, metrics, dimensions, and entities in semantic catalog."
    )
    input_schema: type[BaseModel] = SemanticSearchInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_SEMANTIC_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> SemanticSearchInput:
        try:
            return SemanticSearchInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticSearchInput)
            else SemanticSearchInput.model_validate(validated_input)
        )
        return {"action": "semantic_search", "query": inp.query, "limit": inp.limit}

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticSearchInput)
            else SemanticSearchInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        search_engine = HybridSemanticSearchEngine(context.db_session)
        results = await search_engine.search(
            query=inp.query,
            organization_id=context.organization_id,
            limit=inp.limit,
            object_types=inp.object_types,
            only_published=True,
        )

        data = [
            {
                "object_id": str(r.object_id),
                "object_type": r.object_type.value,
                "name": r.name,
                "description": r.description,
                "definition": r.definition,
                "score": r.score,
                "match_source": r.match_source.value,
                "is_verified": r.is_verified,
            }
            for r in results
        ]

        return ToolOutput(
            success=True,
            data={"results": data, "count": len(data)},
            duration_ms=(time.perf_counter() - t0) * 1000,
        )


class SemanticGetTermTool:
    """Tool retrieving complete business glossary definition and version history."""

    name: str = "semantic.get_term"
    version: str = "v1.0"
    description: str = "Retrieves authoritative definition and versions for a business term."
    input_schema: type[BaseModel] = SemanticGetTermInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_SEMANTIC_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> SemanticGetTermInput:
        try:
            return SemanticGetTermInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticGetTermInput)
            else SemanticGetTermInput.model_validate(validated_input)
        )
        return {"action": "get_term", "term_id": str(inp.term_id)}

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticGetTermInput)
            else SemanticGetTermInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        stmt = (
            select(BusinessTerm)
            .where(
                BusinessTerm.id == inp.term_id,
                BusinessTerm.organization_id == context.organization_id,
            )
            .options(selectinload(BusinessTerm.versions))
        )
        res = await context.db_session.execute(stmt)
        term = res.scalars().first()

        if not term:
            return ToolOutput(
                success=False,
                error_message="Business term not found.",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        versions_data = [
            {
                "version": v.version,
                "definition": v.definition,
                "description": v.description,
                "created_at": v.created_at.isoformat() if v.created_at else "",
            }
            for v in term.versions
        ]

        return ToolOutput(
            success=True,
            data={
                "id": str(term.id),
                "name": term.name,
                "definition": term.definition,
                "description": term.description,
                "category": term.category,
                "status": term.status,
                "version": term.version,
                "owner": term.owner,
                "steward": term.steward,
                "versions": versions_data,
            },
            duration_ms=(time.perf_counter() - t0) * 1000,
        )


class SemanticResolveMetricTool:
    """Tool resolving business metric formula, aggregations, and column bindings."""

    name: str = "semantic.resolve_metric"
    version: str = "v1.0"
    description: str = (
        "Resolves canonical formula, aggregation, and physical column mappings for a metric."
    )
    input_schema: type[BaseModel] = SemanticResolveMetricInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_SEMANTIC_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> SemanticResolveMetricInput:
        try:
            return SemanticResolveMetricInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticResolveMetricInput)
            else SemanticResolveMetricInput.model_validate(validated_input)
        )
        return {"action": "resolve_metric", "metric_name": inp.metric_name}

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticResolveMetricInput)
            else SemanticResolveMetricInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        norm = SemanticTextNormalizer.normalize(inp.metric_name)
        stmt = select(SemanticMetric).where(
            SemanticMetric.organization_id == context.organization_id,
            SemanticMetric.normalized_name == norm,
            SemanticMetric.status == SemanticStatus.PUBLISHED.value,
        )
        if inp.dataset_id:
            stmt = stmt.where(SemanticMetric.dataset_id == inp.dataset_id)

        res = await context.db_session.execute(stmt)
        metric = res.scalars().first()

        if not metric:
            return ToolOutput(
                success=False,
                error_message=f"Published metric '{inp.metric_name}' not found.",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        # Load mappings
        map_stmt = (
            select(SemanticColumnMapping)
            .where(
                SemanticColumnMapping.organization_id == context.organization_id,
                SemanticColumnMapping.semantic_object_type == "metric",
                SemanticColumnMapping.semantic_object_id == metric.id,
            )
            .options(selectinload(SemanticColumnMapping.column))
        )
        mappings = list((await context.db_session.execute(map_stmt)).scalars().all())

        return ToolOutput(
            success=True,
            data={
                "id": str(metric.id),
                "name": metric.name,
                "display_name": metric.display_name,
                "formula": metric.formula,
                "aggregation": metric.aggregation,
                "grain": metric.grain,
                "filters": metric.filters or [],
                "unit": metric.unit,
                "mappings": [
                    {
                        "column": m.column.name if m.column else "",
                        "dataset_id": str(m.dataset_id),
                        "is_verified": m.is_verified,
                        "confidence": m.confidence,
                    }
                    for m in mappings
                ],
            },
            duration_ms=(time.perf_counter() - t0) * 1000,
        )


class SemanticResolveDimensionTool:
    """Tool resolving analytical dimensions and hierarchy levels."""

    name: str = "semantic.resolve_dimension"
    version: str = "v1.0"
    description: str = "Resolves physical column and hierarchy for a semantic dimension."
    input_schema: type[BaseModel] = SemanticResolveDimensionInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_SEMANTIC_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> SemanticResolveDimensionInput:
        try:
            return SemanticResolveDimensionInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticResolveDimensionInput)
            else SemanticResolveDimensionInput.model_validate(validated_input)
        )
        return {"action": "resolve_dimension", "dimension_name": inp.dimension_name}

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticResolveDimensionInput)
            else SemanticResolveDimensionInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        norm = SemanticTextNormalizer.normalize(inp.dimension_name)
        stmt = (
            select(SemanticDimension)
            .where(
                SemanticDimension.organization_id == context.organization_id,
                SemanticDimension.normalized_name == norm,
                SemanticDimension.status == SemanticStatus.PUBLISHED.value,
            )
            .options(selectinload(SemanticDimension.column))
        )
        if inp.dataset_id:
            stmt = stmt.where(SemanticDimension.dataset_id == inp.dataset_id)

        res = await context.db_session.execute(stmt)
        dim = res.scalars().first()

        if not dim:
            return ToolOutput(
                success=False,
                error_message=f"Published dimension '{inp.dimension_name}' not found.",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        return ToolOutput(
            success=True,
            data={
                "id": str(dim.id),
                "name": dim.name,
                "data_type": dim.data_type,
                "dataset_id": str(dim.dataset_id),
                "column_name": dim.column.name if dim.column else "",
                "hierarchy": dim.hierarchy or [],
            },
            duration_ms=(time.perf_counter() - t0) * 1000,
        )


class SemanticGetEntityTool:
    """Tool retrieving business entity definition and primary identifiers."""

    name: str = "semantic.get_entity"
    version: str = "v1.0"
    description: str = "Retrieves semantic entity metadata and primary keys."
    input_schema: type[BaseModel] = SemanticGetEntityInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_SEMANTIC_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> SemanticGetEntityInput:
        try:
            return SemanticGetEntityInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticGetEntityInput)
            else SemanticGetEntityInput.model_validate(validated_input)
        )
        return {"action": "get_entity", "entity_id": str(inp.entity_id)}

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticGetEntityInput)
            else SemanticGetEntityInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        stmt = select(SemanticEntity).where(
            SemanticEntity.id == inp.entity_id,
            SemanticEntity.organization_id == context.organization_id,
        )
        res = await context.db_session.execute(stmt)
        entity = res.scalars().first()

        if not entity:
            return ToolOutput(
                success=False,
                error_message="Semantic entity not found.",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        return ToolOutput(
            success=True,
            data={
                "id": str(entity.id),
                "name": entity.name,
                "dataset_id": str(entity.dataset_id),
                "primary_key": entity.primary_key,
                "display_name_column": entity.display_name_column,
                "description": entity.description,
            },
            duration_ms=(time.perf_counter() - t0) * 1000,
        )


class SemanticGetRelationshipsTool:
    """Tool retrieving entity joins and cardinality relationships."""

    name: str = "semantic.get_relationships"
    version: str = "v1.0"
    description: str = "Retrieves semantic joins and relationships between business entities."
    input_schema: type[BaseModel] = SemanticGetRelationshipsInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_SEMANTIC_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> SemanticGetRelationshipsInput:
        try:
            return SemanticGetRelationshipsInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        return {"action": "get_relationships"}

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticGetRelationshipsInput)
            else SemanticGetRelationshipsInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        stmt = select(SemanticRelationship).where(
            SemanticRelationship.organization_id == context.organization_id,
        )
        if inp.entity_id:
            stmt = stmt.where(
                (SemanticRelationship.from_entity_id == inp.entity_id)
                | (SemanticRelationship.to_entity_id == inp.entity_id)
            )

        res = await context.db_session.execute(stmt)
        rels = list(res.scalars().all())

        data = [
            {
                "id": str(r.id),
                "name": r.name,
                "from_entity_id": str(r.from_entity_id),
                "to_entity_id": str(r.to_entity_id),
                "relationship_type": r.relationship_type,
                "from_column": r.from_column,
                "to_column": r.to_column,
            }
            for r in rels
        ]

        return ToolOutput(
            success=True,
            data={"relationships": data, "count": len(data)},
            duration_ms=(time.perf_counter() - t0) * 1000,
        )


class SemanticGetQueryPlanTool:
    """Tool constructing provenanced semantic query plans from natural language questions."""

    name: str = "semantic.get_query_plan"
    version: str = "v1.0"
    description: str = "Constructs a verified semantic query plan with resolved metrics, dimensions, and SQL hints."
    input_schema: type[BaseModel] = SemanticGetQueryPlanInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_SEMANTIC_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> SemanticGetQueryPlanInput:
        try:
            return SemanticGetQueryPlanInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticGetQueryPlanInput)
            else SemanticGetQueryPlanInput.model_validate(validated_input)
        )
        return {"action": "get_query_plan", "question": inp.question}

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, SemanticGetQueryPlanInput)
            else SemanticGetQueryPlanInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        planner = SemanticQueryPlanner(context.db_session)
        plan = await planner.plan_query(
            question=inp.question,
            organization_id=context.organization_id,
            target_dataset_id=inp.dataset_id,
        )

        return ToolOutput(
            success=True,
            data={
                "question": plan.question,
                "is_authoritative": plan.is_authoritative,
                "dataset_id": str(plan.dataset_id) if plan.dataset_id else None,
                "sql_hint": plan.sql_hint,
                "resolved_metrics": [m.model_dump(mode="json") for m in plan.resolved_metrics],
                "resolved_dimensions": [
                    d.model_dump(mode="json") for d in plan.resolved_dimensions
                ],
                "provenance": plan.provenance,
            },
            duration_ms=(time.perf_counter() - t0) * 1000,
        )

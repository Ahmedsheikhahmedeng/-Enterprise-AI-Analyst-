"""Typed Agent Tools exposing Knowledge Graph reasoning, traversal, and lineage."""

import time
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agents.context import AgentExecutionContext
from app.agents.exceptions import ToolInputValidationError
from app.agents.schemas import ToolRiskLevel
from app.agents.tools.base import ToolOutput
from app.agents.tools.schemas import (
    GraphFindPathInput,
    GraphGetLineageInput,
    GraphGetNeighborsInput,
    GraphGetNodeInput,
    GraphQueryInput,
    GraphSearchInput,
)
from app.knowledge_graph.application.graph_query_service import GraphQueryService
from app.knowledge_graph.application.lineage_service import LineageService
from app.knowledge_graph.application.node_service import NodeService
from app.knowledge_graph.application.path_service import PathService
from app.knowledge_graph.application.traversal_service import TraversalService
from app.knowledge_graph.domain.enums import (
    GraphEdgeType,
    GraphNodeType,
    LineageDirection,
)
from app.knowledge_graph.domain.models import GraphQuery
from app.rbac.catalog import PERM_GRAPH_READ, PERM_GRAPH_TRAVERSE


class GraphSearchTool:
    """Tool discovering entities, terms, and concepts in the knowledge graph."""

    name: str = "graph.search"
    version: str = "v1.0"
    description: str = (
        "Searches vertices and concepts registered in the enterprise knowledge graph."
    )
    input_schema: type[BaseModel] = GraphSearchInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_GRAPH_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> GraphSearchInput:
        try:
            return GraphSearchInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, GraphSearchInput)
            else GraphSearchInput.model_validate(validated_input)
        )
        return {"action": "graph_search", "query": inp.query, "node_type": inp.node_type}

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, GraphSearchInput)
            else GraphSearchInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()
        node_service = NodeService(context.db_session)

        type_filter = GraphNodeType(inp.node_type) if inp.node_type else None
        nodes = await node_service.list_nodes(
            organization_id=context.organization_id,
            node_type=type_filter,
            limit=inp.limit,
        )

        # Filter by text matching if provided
        q_lower = inp.query.lower()
        matched = [n for n in nodes if q_lower in n.name.lower() or q_lower in n.normalized_name]

        data = [
            {
                "id": str(n.id),
                "name": n.name,
                "node_type": n.node_type.value,
                "status": n.status.value,
                "source_object_type": n.source_object_type,
                "source_object_id": str(n.source_object_id),
            }
            for n in matched
        ]

        duration = (time.perf_counter() - t_start) * 1000
        return ToolOutput(
            success=True,
            data={"count": len(data), "nodes": data},
            duration_ms=round(duration, 2),
        )


class GraphGetNodeTool:
    """Tool retrieving complete metadata and properties for a single graph node."""

    name: str = "graph.get_node"
    version: str = "v1.0"
    description: str = "Retrieves vertex details, properties, and provenance by vertex ID."
    input_schema: type[BaseModel] = GraphGetNodeInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_GRAPH_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> GraphGetNodeInput:
        try:
            return GraphGetNodeInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, GraphGetNodeInput)
            else GraphGetNodeInput.model_validate(validated_input)
        )
        return {"action": "graph_get_node", "node_id": str(inp.node_id)}

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, GraphGetNodeInput)
            else GraphGetNodeInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()
        node_service = NodeService(context.db_session)
        try:
            node = await node_service.get_node(inp.node_id, context.organization_id)
            duration = (time.perf_counter() - t_start) * 1000
            return ToolOutput(
                success=True,
                data={
                    "id": str(node.id),
                    "name": node.name,
                    "node_type": node.node_type.value,
                    "status": node.status.value,
                    "metadata": node.metadata,
                    "source_object_type": node.source_object_type,
                    "source_object_id": str(node.source_object_id),
                    "version": node.version,
                },
                duration_ms=round(duration, 2),
            )
        except Exception as exc:
            duration = (time.perf_counter() - t_start) * 1000
            return ToolOutput(
                success=False,
                error_message=str(exc),
                duration_ms=round(duration, 2),
            )


class GraphGetNeighborsTool:
    """Tool exploring 1-to-4 hop neighbor topology around a vertex."""

    name: str = "graph.get_neighbors"
    version: str = "v1.0"
    description: str = "Explores neighboring vertices and connecting edges up to depth 4."
    input_schema: type[BaseModel] = GraphGetNeighborsInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_GRAPH_TRAVERSE
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> GraphGetNeighborsInput:
        try:
            return GraphGetNeighborsInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, GraphGetNeighborsInput)
            else GraphGetNeighborsInput.model_validate(validated_input)
        )
        return {"action": "graph_get_neighbors", "node_id": str(inp.node_id), "depth": inp.depth}

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, GraphGetNeighborsInput)
            else GraphGetNeighborsInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()
        traversal_service = TraversalService(context.db_session)

        edge_types = [GraphEdgeType(et) for et in inp.edge_types] if inp.edge_types else None
        traversal = await traversal_service.get_neighbors(
            node_id=inp.node_id,
            organization_id=context.organization_id,
            depth=inp.depth,
            edge_types=edge_types,
            only_published=True,
        )

        nodes_data = [
            {"id": str(n.id), "name": n.name, "type": n.node_type.value}
            for n in traversal.visited_nodes
        ]
        edges_data = [
            {
                "id": str(e.id),
                "source": str(e.source_node_id),
                "target": str(e.target_node_id),
                "type": e.edge_type.value,
                "confidence": e.confidence,
                "is_verified": e.is_verified,
            }
            for e in traversal.visited_edges
        ]

        duration = (time.perf_counter() - t_start) * 1000
        return ToolOutput(
            success=True,
            data={"nodes": nodes_data, "edges": edges_data, "depth": traversal.depth},
            duration_ms=round(duration, 2),
        )


class GraphFindPathTool:
    """Tool discovering multi-hop relationship paths between two specific vertices."""

    name: str = "graph.find_path"
    version: str = "v1.0"
    description: str = "Finds ranked multi-hop paths connecting two knowledge graph vertices."
    input_schema: type[BaseModel] = GraphFindPathInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_GRAPH_TRAVERSE
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> GraphFindPathInput:
        try:
            return GraphFindPathInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, GraphFindPathInput)
            else GraphFindPathInput.model_validate(validated_input)
        )
        return {
            "action": "graph_find_path",
            "start_node_id": str(inp.start_node_id),
            "target_node_id": str(inp.target_node_id),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, GraphFindPathInput)
            else GraphFindPathInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()
        path_service = PathService(context.db_session)

        paths = await path_service.find_paths(
            start_node_id=inp.start_node_id,
            target_node_id=inp.target_node_id,
            organization_id=context.organization_id,
            max_depth=inp.max_depth,
            only_published=True,
            only_verified=inp.only_verified,
        )

        formatted_paths = [
            {
                "depth": p.depth,
                "confidence": p.confidence,
                "verified_ratio": p.verified_ratio,
                "path_nodes": [n.name for n in p.nodes],
                "edge_types": [e.edge_type.value for e in p.edges],
            }
            for p in paths
        ]

        duration = (time.perf_counter() - t_start) * 1000
        return ToolOutput(
            success=True,
            data={"paths_count": len(formatted_paths), "paths": formatted_paths},
            duration_ms=round(duration, 2),
        )


class GraphQueryTool:
    """Tool executing concept reasoning queries from natural language or concept mentions."""

    name: str = "graph.query"
    version: str = "v1.0"
    description: str = "Executes concept-to-concept relationship resolution across the graph."
    input_schema: type[BaseModel] = GraphQueryInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_GRAPH_TRAVERSE
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> GraphQueryInput:
        try:
            return GraphQueryInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, GraphQueryInput)
            else GraphQueryInput.model_validate(validated_input)
        )
        return {
            "action": "graph_query",
            "start_entity": inp.start_entity,
            "target_concept": inp.target_concept,
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, GraphQueryInput)
            else GraphQueryInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()
        query_service = GraphQueryService(context.db_session)

        g_query = GraphQuery(
            start_entity=inp.start_entity,
            target_concept=inp.target_concept,
            max_depth=inp.max_depth,
            only_published=True,
        )

        result = await query_service.execute_query(g_query, context.organization_id)

        paths_data = [
            {
                "depth": p.depth,
                "confidence": p.confidence,
                "nodes": [n.name for n in p.nodes],
                "relationships": [e.edge_type.value for e in p.edges],
            }
            for p in result.paths
        ]

        duration = (time.perf_counter() - t_start) * 1000
        return ToolOutput(
            success=True,
            data={
                "confidence": result.confidence,
                "paths": paths_data,
                "provenance": {
                    "graph_version": result.provenance.graph_version,
                    "is_verified": result.provenance.verified_status,
                },
            },
            duration_ms=round(duration, 2),
        )


class GraphGetLineageTool:
    """Tool tracing forward or reverse concept and column lineage."""

    name: str = "graph.get_lineage"
    version: str = "v1.0"
    description: str = "Traces forward or reverse physical and semantic lineage from a vertex."
    input_schema: type[BaseModel] = GraphGetLineageInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_GRAPH_READ
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    async def validate(self, tool_input: dict[str, Any]) -> GraphGetLineageInput:
        try:
            return GraphGetLineageInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, GraphGetLineageInput)
            else GraphGetLineageInput.model_validate(validated_input)
        )
        return {
            "action": "graph_get_lineage",
            "node_id": str(inp.node_id),
            "direction": inp.direction,
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, GraphGetLineageInput)
            else GraphGetLineageInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()
        lineage_service = LineageService(context.db_session)

        direction = (
            LineageDirection.REVERSE
            if inp.direction.upper() == "REVERSE"
            else LineageDirection.FORWARD
        )
        result = await lineage_service.get_lineage(
            node_id=inp.node_id,
            organization_id=context.organization_id,
            direction=direction,
            max_depth=inp.max_depth,
        )

        duration = (time.perf_counter() - t_start) * 1000
        return ToolOutput(
            success=True,
            data={
                "root_node": result.root_node.name,
                "direction": result.direction.value,
                "lineage_paths": result.lineage_paths,
                "nodes_count": len(result.nodes),
            },
            duration_ms=round(duration, 2),
        )

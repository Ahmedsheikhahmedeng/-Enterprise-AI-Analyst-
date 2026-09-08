"""Typed Tool Registry for cataloging, discovery, and pre-execution schema resolution."""

from app.agents.exceptions import ToolNotFoundError
from app.agents.tools.analyst import AnalystTool
from app.agents.tools.base import AgentTool
from app.agents.tools.dataset import (
    DatasetGetTool,
    DatasetListTool,
    DatasetProfileTool,
    DatasetQualityTool,
    DatasetVersionsTool,
)
from app.agents.tools.datasource import (
    DataSourceListTool,
    DataSourcePreviewTool,
    DataSourceQueryTool,
    DataSourceSchemaTool,
)
from app.agents.tools.evaluation import EvaluationTool
from app.agents.tools.knowledge_graph import (
    GraphFindPathTool,
    GraphGetLineageTool,
    GraphGetNeighborsTool,
    GraphGetNodeTool,
    GraphQueryTool,
    GraphSearchTool,
)
from app.agents.tools.orchestrator import AskEnterpriseTool
from app.agents.tools.rag import RAGTool
from app.agents.tools.report import ReportTool
from app.agents.tools.semantic import (
    SemanticGetEntityTool,
    SemanticGetQueryPlanTool,
    SemanticGetRelationshipsTool,
    SemanticGetTermTool,
    SemanticResolveDimensionTool,
    SemanticResolveMetricTool,
    SemanticSearchTool,
)
from app.agents.tools.sql import SQLTool


class ToolRegistry:
    """Thread-safe registry of all authorized typed agent tools."""

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        """Register a typed tool implementation."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> AgentTool:
        """Retrieve tool by name; raises ToolNotFoundError if unregistered."""
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def list_tools(self) -> list[AgentTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def tool_names(self) -> set[str]:
        """Return all registered tool names."""
        return set(self._tools.keys())


_global_tool_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Singleton getter returning initialized ToolRegistry with default enterprise tools."""
    global _global_tool_registry
    if _global_tool_registry is None:
        reg = ToolRegistry()
        reg.register(AnalystTool())
        reg.register(SQLTool())
        reg.register(RAGTool())
        reg.register(ReportTool())
        reg.register(EvaluationTool())
        reg.register(DataSourceListTool())
        reg.register(DataSourceSchemaTool())
        reg.register(DataSourcePreviewTool())
        reg.register(DataSourceQueryTool())
        reg.register(DatasetListTool())
        reg.register(DatasetGetTool())
        reg.register(DatasetProfileTool())
        reg.register(DatasetVersionsTool())
        reg.register(DatasetQualityTool())
        reg.register(SemanticSearchTool())
        reg.register(SemanticGetTermTool())
        reg.register(SemanticResolveMetricTool())
        reg.register(SemanticResolveDimensionTool())
        reg.register(SemanticGetEntityTool())
        reg.register(SemanticGetRelationshipsTool())
        reg.register(SemanticGetQueryPlanTool())
        reg.register(GraphSearchTool())
        reg.register(GraphGetNodeTool())
        reg.register(GraphGetNeighborsTool())
        reg.register(GraphFindPathTool())
        reg.register(GraphQueryTool())
        reg.register(GraphGetLineageTool())
        reg.register(AskEnterpriseTool())
        _global_tool_registry = reg
    return _global_tool_registry

"""Agent profiles defining allowed tools and operational constraints for agent types."""

from dataclasses import dataclass, field

from app.agents.schemas import AgentType


@dataclass
class AgentProfile:
    """Bounded operational envelope for a specific agent role."""

    agent_type: AgentType
    allowed_tools: set[str]
    name: str = ""
    max_steps: int = 20
    max_tokens: int = 50000
    max_cost_usd: float = 2.0
    requires_approval_tools: set[str] = field(default_factory=set)
    system_policy_version: str = "v1.0"

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.agent_type.value

    @property
    def max_cost(self) -> float:
        return self.max_cost_usd

    @property
    def requires_approval(self) -> bool:
        return len(self.requires_approval_tools) > 0


# Standard default profiles
PROFILES: dict[AgentType, AgentProfile] = {
    AgentType.ANALYST_AGENT: AgentProfile(
        agent_type=AgentType.ANALYST_AGENT,
        allowed_tools={
            "analyst.query",
            "sql.query",
            "rag.retrieve",
            "report.create",
            "datasource.list",
            "datasource.schema",
            "datasource.preview",
            "datasource.query",
            "dataset.list",
            "dataset.get",
            "dataset.profile",
            "dataset.versions",
            "dataset.quality",
            "semantic.search",
            "semantic.get_term",
            "semantic.resolve_metric",
            "semantic.resolve_dimension",
            "semantic.get_entity",
            "semantic.get_relationships",
            "semantic.get_query_plan",
            "graph.search",
            "graph.get_node",
            "graph.get_neighbors",
            "graph.find_path",
            "graph.query",
            "graph.get_lineage",
        },
        max_steps=20,
        max_tokens=50000,
        max_cost_usd=2.0,
        requires_approval_tools={"report.create"},
    ),
    AgentType.RESEARCH_AGENT: AgentProfile(
        agent_type=AgentType.RESEARCH_AGENT,
        allowed_tools={
            "rag.retrieve",
            "sql.query",
            "datasource.list",
            "datasource.schema",
            "datasource.preview",
            "datasource.query",
            "dataset.list",
            "dataset.get",
            "dataset.profile",
            "dataset.versions",
            "dataset.quality",
            "semantic.search",
            "semantic.get_term",
            "semantic.resolve_metric",
            "semantic.resolve_dimension",
            "semantic.get_entity",
            "semantic.get_relationships",
            "semantic.get_query_plan",
            "graph.search",
            "graph.get_node",
            "graph.get_neighbors",
            "graph.find_path",
            "graph.query",
            "graph.get_lineage",
        },
        max_steps=15,
        max_tokens=40000,
        max_cost_usd=1.5,
        requires_approval_tools=set(),
    ),
    AgentType.REPORT_AGENT: AgentProfile(
        agent_type=AgentType.REPORT_AGENT,
        allowed_tools={"analyst.query", "report.create"},
        max_steps=10,
        max_tokens=30000,
        max_cost_usd=1.0,
        requires_approval_tools={"report.create"},
    ),
    AgentType.EVALUATION_AGENT: AgentProfile(
        agent_type=AgentType.EVALUATION_AGENT,
        allowed_tools={"evaluation.run"},
        max_steps=5,
        max_tokens=25000,
        max_cost_usd=1.0,
        requires_approval_tools={"evaluation.run"},
    ),
}


def get_agent_profile(agent_type: str | AgentType) -> AgentProfile:
    """Retrieve profile definition for given agent type."""
    t = AgentType(str(agent_type))
    return PROFILES.get(t, PROFILES[AgentType.ANALYST_AGENT])

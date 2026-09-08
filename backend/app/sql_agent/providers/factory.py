"""Factory for constructing SQL generation providers."""

from app.sql_agent.config import SQLAgentConfig, get_sql_agent_config
from app.sql_agent.providers.base import SQLGenerationProvider
from app.sql_agent.providers.deterministic import DeterministicSQLProvider
from app.sql_agent.providers.gateway import GatewaySQLProvider


class SQLProviderFactory:
    """Instantiates SQL generation provider based on configuration."""

    @staticmethod
    def create(config: SQLAgentConfig | None = None) -> SQLGenerationProvider:
        """Construct SQL provider matching configuration or fallback to deterministic."""
        cfg = config or get_sql_agent_config()

        if cfg.provider in ("openai", "gateway"):
            return GatewaySQLProvider(model_name=cfg.model)

        return DeterministicSQLProvider(model_name=cfg.model)

"""Agent configuration settings and operational thresholds."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    """Runtime limits, default budgets, and timeouts for Enterprise Agent orchestration."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        case_sensitive=False,
        extra="ignore",
    )

    # Step budgets
    default_max_steps: int = Field(default=20, ge=1, le=100)
    default_max_tool_calls: int = Field(default=20, ge=1, le=100)

    # Time budgets
    default_duration_seconds: float = Field(default=300.0, ge=5.0, le=3600.0)
    step_timeout_seconds: float = Field(default=60.0, ge=2.0, le=600.0)
    tool_timeout_seconds: float = Field(default=45.0, ge=1.0, le=300.0)

    # Token & Cost budgets
    default_max_tokens: int = Field(default=50000, ge=100, le=1000000)
    default_max_cost_usd: float = Field(default=2.0, ge=0.01, le=100.0)

    # Loop Detection
    loop_detection_window: int = Field(default=5, ge=2, le=20)
    loop_detection_threshold: int = Field(default=3, ge=2, le=10)

    # Output Limits
    max_output_bytes: int = Field(default=1024 * 1024, ge=1024)  # 1MB
    max_context_tokens: int = Field(default=16000, ge=500)

    # Policy & Versions
    planner_version: str = "v1.0"
    prompt_version: str = "v1.0"
    system_policy_version: str = "v1.0"


@lru_cache(maxsize=1)
def get_agent_config() -> AgentConfig:
    """Return cached singleton AgentConfig instance."""
    return AgentConfig()

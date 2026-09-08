"""Deep instrumentation for Enterprise Agent Runtime."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry


class AgentInstrumentation:
    """Instruments Agent sessions, tool calls, approvals, budgets, and state transitions."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_session_started(self, agent_type: str) -> None:
        labels = {"agent_type": agent_type.lower()}
        self.metrics.increment(
            "agent_sessions_total",
            value=1.0,
            labels=labels,
            description="Total agent sessions started",
        )

    def record_session_completed(
        self, agent_type: str, status: str, duration_ms: float, tokens: int, cost: float
    ) -> None:
        labels = {
            "agent_type": agent_type.lower(),
            "status": status.lower(),
        }
        if status.lower() == "completed":
            self.metrics.increment(
                "agent_sessions_completed_total",
                value=1.0,
                labels={"agent_type": agent_type.lower()},
                description="Total successfully completed agent sessions",
            )
        elif status.lower() == "cancelled":
            self.metrics.increment(
                "agent_sessions_cancelled_total",
                value=1.0,
                labels={"agent_type": agent_type.lower()},
                description="Total cancelled agent sessions",
            )
        elif status.lower() in ("failed", "error"):
            self.metrics.increment(
                "agent_sessions_failed_total",
                value=1.0,
                labels={"agent_type": agent_type.lower()},
                description="Total failed agent sessions",
            )
        elif status.lower() == "budget_exceeded":
            self.metrics.increment(
                "agent_budget_exceeded_total",
                value=1.0,
                labels={"agent_type": agent_type.lower()},
                description="Total sessions terminated due to budget exhaustion",
            )

        self.metrics.observe(
            "agent_duration_ms",
            value=duration_ms,
            labels=labels,
            description="Execution duration for agent sessions",
        )
        self.metrics.increment(
            "agent_tokens_total",
            value=float(tokens),
            labels=labels,
            description="Total tokens consumed across agent sessions",
        )
        self.metrics.increment(
            "agent_cost_total",
            value=cost,
            labels=labels,
            description="Total USD cost incurred by agent sessions",
        )

    def record_step_executed(self, agent_type: str, status: str) -> None:
        self.metrics.increment(
            "agent_steps_total",
            value=1.0,
            labels={"agent_type": agent_type.lower(), "status": status.lower()},
            description="Total individual agent steps executed",
        )

    def record_tool_call(self, tool_name: str, status: str, duration_ms: float) -> None:
        labels = {"tool_name": tool_name.lower(), "status": status.lower()}
        self.metrics.increment(
            "agent_tool_calls_total",
            value=1.0,
            labels=labels,
            description="Total agent tool invocations",
        )
        if status.lower() in ("failed", "error"):
            self.metrics.increment(
                "agent_tool_failures_total",
                value=1.0,
                labels={"tool_name": tool_name.lower()},
                description="Total failed agent tool invocations",
            )

    def record_approval_wait(self, tool_name: str, wait_ms: float) -> None:
        self.metrics.observe(
            "agent_approval_wait_ms",
            value=wait_ms,
            labels={"tool_name": tool_name.lower()},
            description="Wait time in ms for human operator approval",
        )


_global_agent_instrumentation: AgentInstrumentation | None = None


def get_agent_instrumentation() -> AgentInstrumentation:
    global _global_agent_instrumentation
    if _global_agent_instrumentation is None:
        _global_agent_instrumentation = AgentInstrumentation()
    return _global_agent_instrumentation

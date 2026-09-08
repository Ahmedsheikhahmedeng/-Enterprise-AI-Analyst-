"""Deterministic state machine governing AgentSession lifecycle transitions."""

from app.agents.exceptions import AgentStateTransitionError
from app.agents.schemas import AgentStatus


class AgentStateMachine:
    """Enforces valid explicit status transitions for AgentSession."""

    # Explicit allowed transitions mapping: source_state -> set of valid target_states
    _ALLOWED_TRANSITIONS: dict[AgentStatus, set[AgentStatus]] = {
        AgentStatus.CREATED: {
            AgentStatus.PLANNING,
            AgentStatus.CANCELLED,
            AgentStatus.FAILED,
        },
        AgentStatus.PLANNING: {
            AgentStatus.PLANNED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
        },
        AgentStatus.PLANNED: {
            AgentStatus.AWAITING_APPROVAL,
            AgentStatus.EXECUTING,
            AgentStatus.CANCELLED,
            AgentStatus.FAILED,
        },
        AgentStatus.AWAITING_APPROVAL: {
            AgentStatus.EXECUTING,
            AgentStatus.CANCELLED,
            AgentStatus.FAILED,
            AgentStatus.PAUSED,
        },
        AgentStatus.EXECUTING: {
            AgentStatus.AWAITING_APPROVAL,
            AgentStatus.PAUSED,
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
            AgentStatus.BUDGET_EXCEEDED,
        },
        AgentStatus.PAUSED: {
            AgentStatus.EXECUTING,
            AgentStatus.CANCELLED,
            AgentStatus.FAILED,
        },
        # Terminal states: NO transitions back to executing allowed
        AgentStatus.COMPLETED: set(),
        AgentStatus.CANCELLED: set(),
        AgentStatus.FAILED: set(),
        AgentStatus.BUDGET_EXCEEDED: set(),
    }

    @classmethod
    def validate_transition(
        cls, current_status: str | AgentStatus, target_status: str | AgentStatus
    ) -> None:
        """Verify that transitioning from current_status to target_status is valid."""
        try:
            curr = AgentStatus(str(current_status))
            target = AgentStatus(str(target_status))
        except ValueError as e:
            raise AgentStateTransitionError(str(current_status), str(target_status)) from e

        allowed = cls._ALLOWED_TRANSITIONS.get(curr, set())
        if target not in allowed:
            raise AgentStateTransitionError(curr.value, target.value)

    @classmethod
    def is_terminal(cls, status: str | AgentStatus) -> bool:
        """Check if state is terminal."""
        try:
            st = AgentStatus(str(status))
            return len(cls._ALLOWED_TRANSITIONS.get(st, set())) == 0
        except ValueError:
            return False

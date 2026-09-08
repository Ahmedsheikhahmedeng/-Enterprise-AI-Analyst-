"""Standard domain exceptions for Enterprise Agent Runtime."""

from typing import Any
from uuid import UUID


class AgentError(Exception):
    """Base exception for all agent runtime errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AgentSessionNotFoundError(AgentError):
    """Raised when an agent session cannot be located."""

    def __init__(self, session_id: UUID) -> None:
        super().__init__(
            f"Agent session '{session_id}' not found.",
            {"session_id": str(session_id)},
        )


class AgentStateTransitionError(AgentError):
    """Raised when an illegal state machine transition is attempted."""

    def __init__(self, current_status: str, target_status: str) -> None:
        super().__init__(
            f"Illegal state transition from '{current_status}' to '{target_status}'.",
            {"current_status": current_status, "target_status": target_status},
        )


class PlanValidationError(AgentError):
    """Raised when an agent execution plan fails validation."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(f"Plan validation failed: {message}", details)


class ToolNotFoundError(AgentError):
    """Raised when an agent requests a tool not in the registry."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(
            f"Tool '{tool_name}' is not registered.",
            {"tool_name": tool_name},
        )


class ToolAuthorizationError(AgentError):
    """Raised when a tool is disallowed by policy, RBAC, or profile allowlist."""

    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__(
            f"Tool '{tool_name}' unauthorized: {reason}",
            {"tool_name": tool_name, "reason": reason},
        )


class ToolInputValidationError(AgentError):
    """Raised when tool input parameters fail schema validation."""

    def __init__(self, tool_name: str, message: str, errors: Any = None) -> None:
        super().__init__(
            f"Invalid input for tool '{tool_name}': {message}",
            {"tool_name": tool_name, "errors": errors},
        )


class ToolExecutionError(AgentError):
    """Raised when a tool execution fails."""

    def __init__(self, tool_name: str, message: str, retryable: bool = False) -> None:
        super().__init__(
            f"Execution error in tool '{tool_name}': {message}",
            {"tool_name": tool_name, "retryable": retryable},
        )
        self.retryable = retryable


class BudgetExceededError(AgentError):
    """Raised when step, time, token, or cost budget is exhausted."""

    def __init__(self, budget_type: str, limit: Any, consumed: Any) -> None:
        super().__init__(
            f"Agent budget exceeded for '{budget_type}'. Limit: {limit}, Consumed: {consumed}",
            {"budget_type": budget_type, "limit": limit, "consumed": consumed},
        )
        self.budget_type = budget_type


class ApprovalRequiredError(AgentError):
    """Raised when a step requires human approval before proceeding."""

    def __init__(self, session_id: UUID, step_id: UUID, tool_name: str) -> None:
        super().__init__(
            f"Step '{step_id}' using tool '{tool_name}' requires approval.",
            {"session_id": str(session_id), "step_id": str(step_id), "tool_name": tool_name},
        )


class ApprovalDeniedError(AgentError):
    """Raised when an approval request was rejected by an operator."""

    def __init__(self, approval_id: UUID, reason: str) -> None:
        super().__init__(
            f"Approval '{approval_id}' was rejected: {reason}",
            {"approval_id": str(approval_id), "reason": reason},
        )


class LoopDetectedError(AgentError):
    """Raised when repeated identical tool calls are detected."""

    def __init__(self, tool_name: str, count: int) -> None:
        super().__init__(
            f"Loop detected: tool '{tool_name}' executed {count} times with identical input.",
            {"tool_name": tool_name, "count": count},
        )


class AgentCancellationError(AgentError):
    """Raised when execution terminates due to explicit cancellation."""

    def __init__(self, session_id: UUID) -> None:
        super().__init__(
            f"Agent session '{session_id}' was cancelled.",
            {"session_id": str(session_id)},
        )

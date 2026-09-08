"""Pre-flight authorization and risk verification policy for agent tool calls."""

from uuid import UUID

from app.agents.exceptions import ToolAuthorizationError
from app.agents.schemas import ToolRiskLevel


class AgentToolPolicy:
    """Server-side policy enforcing permissions, risk tier, profile allowlist, and tenant boundaries."""

    def __init__(
        self, allowed_tools: set[str] | None = None, allow_high_risk: bool = False
    ) -> None:
        self.allowed_tools = allowed_tools
        self.allow_high_risk = allow_high_risk

    def authorize_tool(
        self,
        tool_name: str,
        tool_risk_level: ToolRiskLevel,
        required_permission: str,
        user_permissions: set[str],
        organization_id: UUID,
        target_org_id: UUID | None = None,
        session_id: UUID | None = None,
        session_status: str | None = None,
    ) -> None:
        """Validate whether a tool can be executed by the current user within tenant context."""
        # 1. Profile tool allowlist check (tool allowed?)
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            raise ToolAuthorizationError(
                tool_name, f"Tool is not in profile allowlist: {self.allowed_tools}"
            )

        # 2. Risk check (risk allowed?)
        if tool_risk_level == ToolRiskLevel.HIGH_RISK and not self.allow_high_risk:
            raise ToolAuthorizationError(
                tool_name, "High-risk tools are prohibited in current environment"
            )

        # 3. RBAC permission check (user allowed?)
        if required_permission not in user_permissions:
            raise ToolAuthorizationError(
                tool_name, f"User lacks required permission '{required_permission}'"
            )

        # 4. Strict tenant isolation check (tenant allowed?)
        if target_org_id is not None and target_org_id != organization_id:
            raise ToolAuthorizationError(tool_name, "Cross-tenant resource invocation attempted")

        # 5. Session state check (state allowed / session allowed?)
        if session_status is not None and session_status not in ("executing", "running", "planned"):
            raise ToolAuthorizationError(
                tool_name, f"Tool execution disallowed in session state '{session_status}'"
            )

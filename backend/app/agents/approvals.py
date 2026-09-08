"""Operator approval management and lifecycle governance for sensitive tool execution."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.exceptions import ApprovalDeniedError, ApprovalRequiredError
from app.agents.models import ApprovalRequest
from app.agents.schemas import ApprovalStatus


class ApprovalManager:
    """Manages creation, verification, and resolution of approval requests."""

    async def create_request(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        step_id: UUID,
        organization_id: UUID,
        reason: str,
        requested_by: UUID | None = None,
    ) -> ApprovalRequest:
        """Create a pending approval gate record."""
        req = ApprovalRequest(
            session_id=session_id,
            step_id=step_id,
            organization_id=organization_id,
            requested_by=requested_by,
            status=ApprovalStatus.PENDING.value,
            reason=reason,
        )
        db_session.add(req)
        await db_session.flush()
        return req

    async def get_request(
        self,
        db_session: AsyncSession,
        approval_id: UUID,
        organization_id: UUID,
    ) -> ApprovalRequest | None:
        """Retrieve approval request within tenant boundary."""
        stmt = select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.organization_id == organization_id,
        )
        res = await db_session.execute(stmt)
        return res.scalars().first()

    async def list_session_approvals(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        organization_id: UUID,
    ) -> list[ApprovalRequest]:
        """List all approvals for a given session."""
        stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.session_id == session_id,
                ApprovalRequest.organization_id == organization_id,
            )
            .order_by(ApprovalRequest.created_at.asc())
        )
        res = await db_session.execute(stmt)
        return list(res.scalars().all())

    async def resolve(
        self,
        db_session: AsyncSession,
        approval: ApprovalRequest,
        decision: ApprovalStatus,
        operator_user_id: UUID,
        reason: str = "",
    ) -> ApprovalRequest:
        """Approve or reject a pending approval request."""
        approval.status = decision.value
        approval.approved_by = operator_user_id
        approval.resolved_at = datetime.now(UTC)
        if reason:
            approval.reason = f"{approval.reason} | Decision note: {reason}"
        await db_session.flush()
        return approval

    async def ensure_approved_or_raise(
        self,
        db_session: AsyncSession,
        session_id: UUID,
        step_id: UUID,
        tool_name: str,
        requires_approval: bool,
    ) -> None:
        """Check if approved request exists; raise ApprovalRequiredError or ApprovalDeniedError otherwise."""
        if not requires_approval:
            return

        stmt = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.session_id == session_id,
                ApprovalRequest.step_id == step_id,
            )
            .order_by(ApprovalRequest.created_at.desc())
        )
        res = await db_session.execute(stmt)
        req = res.scalars().first()

        if not req or req.status == ApprovalStatus.PENDING.value:
            raise ApprovalRequiredError(session_id=session_id, step_id=step_id, tool_name=tool_name)
        if req.status in (ApprovalStatus.REJECTED.value, ApprovalStatus.EXPIRED.value):
            raise ApprovalDeniedError(approval_id=req.id, reason=req.reason)

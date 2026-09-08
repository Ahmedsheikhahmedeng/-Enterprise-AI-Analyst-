"""SQLAlchemy repository for Enterprise Governance entities with strict tenant isolation."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.governance import (
    ApprovalCommentModel,
    ApprovalDecisionModel,
    ApprovalRequestModel,
    ApprovalVoteModel,
    GovernancePolicyModel,
)

logger = logging.getLogger(__name__)


class GovernanceRepository:
    """Manages transactional persistence and tenant-isolated retrieval for governance records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -------------------------------------------------------------------------
    # Governance Policies
    # -------------------------------------------------------------------------

    async def get_active_policy(self, organization_id: uuid.UUID) -> GovernancePolicyModel | None:
        """Fetch the latest active policy for the organization."""
        stmt = (
            select(GovernancePolicyModel)
            .where(
                GovernancePolicyModel.organization_id == organization_id,
                GovernancePolicyModel.status == "ACTIVE",
            )
            .order_by(desc(GovernancePolicyModel.policy_version))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_policy_by_version(
        self, organization_id: uuid.UUID, version: int
    ) -> GovernancePolicyModel | None:
        """Fetch a specific version of tenant governance policy."""
        stmt = select(GovernancePolicyModel).where(
            GovernancePolicyModel.organization_id == organization_id,
            GovernancePolicyModel.policy_version == version,
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_policies(
        self, organization_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[GovernancePolicyModel]:
        """List historical policy versions for organization."""
        stmt = (
            select(GovernancePolicyModel)
            .where(GovernancePolicyModel.organization_id == organization_id)
            .order_by(desc(GovernancePolicyModel.policy_version))
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create_policy(
        self,
        organization_id: uuid.UUID,
        rules: dict[str, Any],
        policy_version: int,
        status: str = "ACTIVE",
        created_by: uuid.UUID | None = None,
        approved_by: uuid.UUID | None = None,
    ) -> GovernancePolicyModel:
        """Persist a new governance policy version."""
        record = GovernancePolicyModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            rules=rules,
            policy_version=policy_version,
            status=status,
            created_by=created_by,
            approved_by=approved_by,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    # -------------------------------------------------------------------------
    # Approval Requests
    # -------------------------------------------------------------------------

    async def create_request(
        self,
        request_id: uuid.UUID,
        organization_id: uuid.UUID,
        request_type: str,
        requester_id: uuid.UUID,
        resource_type: str,
        resource_id: str | None,
        risk_level: str,
        risk_score: float,
        status: str,
        reason: str | None,
        context: dict[str, Any] | None,
        action_hash: str | None,
        resource_hash: str | None,
        policy_version: int,
        expires_at: datetime,
    ) -> ApprovalRequestModel:
        """Create a new approval request record."""
        record = ApprovalRequestModel(
            id=request_id,
            organization_id=organization_id,
            request_type=request_type,
            requester_id=requester_id,
            resource_type=resource_type,
            resource_id=resource_id,
            risk_level=risk_level,
            risk_score=risk_score,
            status=status,
            reason=reason,
            context=context,
            action_hash=action_hash,
            resource_hash=resource_hash,
            policy_version=policy_version,
            expires_at=expires_at,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_request(
        self, organization_id: uuid.UUID, request_id: uuid.UUID
    ) -> ApprovalRequestModel | None:
        """Retrieve approval request with eager loaded votes, decisions, and comments."""
        stmt = (
            select(ApprovalRequestModel)
            .where(
                ApprovalRequestModel.id == request_id,
                ApprovalRequestModel.organization_id == organization_id,
            )
            .options(
                selectinload(ApprovalRequestModel.votes),
                selectinload(ApprovalRequestModel.decisions),
                selectinload(ApprovalRequestModel.comments),
            )
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_requests(
        self,
        organization_id: uuid.UUID,
        status: str | None = None,
        request_type: str | None = None,
        risk_level: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalRequestModel]:
        """List approval requests within tenant boundary with optional filtering."""
        stmt = select(ApprovalRequestModel).where(
            ApprovalRequestModel.organization_id == organization_id
        )
        if status:
            stmt = stmt.where(ApprovalRequestModel.status == status)
        if request_type:
            stmt = stmt.where(ApprovalRequestModel.request_type == request_type)
        if risk_level:
            stmt = stmt.where(ApprovalRequestModel.risk_level == risk_level)

        stmt = (
            stmt.options(
                selectinload(ApprovalRequestModel.votes),
                selectinload(ApprovalRequestModel.comments),
                selectinload(ApprovalRequestModel.decisions),
            )
            .order_by(desc(ApprovalRequestModel.created_at))
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_high_risk_requests(
        self, organization_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[ApprovalRequestModel]:
        """List HIGH and CRITICAL risk approval requests."""
        stmt = (
            select(ApprovalRequestModel)
            .where(
                ApprovalRequestModel.organization_id == organization_id,
                ApprovalRequestModel.risk_level.in_(["HIGH", "CRITICAL"]),
            )
            .options(
                selectinload(ApprovalRequestModel.votes),
                selectinload(ApprovalRequestModel.comments),
                selectinload(ApprovalRequestModel.decisions),
            )
            .order_by(desc(ApprovalRequestModel.created_at))
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_expired_pending_requests(
        self, now: datetime | None = None
    ) -> list[ApprovalRequestModel]:
        """Fetch all PENDING or IN_REVIEW requests whose expires_at is past now."""
        current_time = now or datetime.now(UTC)
        stmt = select(ApprovalRequestModel).where(
            ApprovalRequestModel.status.in_(["PENDING", "IN_REVIEW"]),
            ApprovalRequestModel.expires_at <= current_time,
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # Votes & Quorum
    # -------------------------------------------------------------------------

    async def create_vote(
        self,
        organization_id: uuid.UUID,
        approval_request_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        decision: str,
        comment: str | None = None,
    ) -> ApprovalVoteModel:
        """Submit a reviewer vote."""
        vote = ApprovalVoteModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            approval_request_id=approval_request_id,
            reviewer_id=reviewer_id,
            decision=decision,
            comment=comment,
        )
        self.session.add(vote)
        await self.session.flush()
        return vote

    async def get_votes_for_request(
        self, organization_id: uuid.UUID, approval_request_id: uuid.UUID
    ) -> list[ApprovalVoteModel]:
        """Retrieve all submitted votes for a specific request."""
        stmt = (
            select(ApprovalVoteModel)
            .where(
                ApprovalVoteModel.organization_id == organization_id,
                ApprovalVoteModel.approval_request_id == approval_request_id,
            )
            .order_by(ApprovalVoteModel.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # -------------------------------------------------------------------------
    # Decisions
    # -------------------------------------------------------------------------

    async def create_decision(
        self,
        organization_id: uuid.UUID,
        request_id: uuid.UUID,
        decision: str,
        reviewer_ids: list[str],
        policy_version: int,
        risk_score: float,
        decision_hash: str,
    ) -> ApprovalDecisionModel:
        """Create an immutable decision audit record."""
        rec = ApprovalDecisionModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            request_id=request_id,
            decision=decision,
            reviewer_ids=reviewer_ids,
            policy_version=policy_version,
            risk_score=risk_score,
            decision_hash=decision_hash,
        )
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def get_decision_by_request(
        self, organization_id: uuid.UUID, request_id: uuid.UUID
    ) -> ApprovalDecisionModel | None:
        """Retrieve the immutable decision record for a request."""
        stmt = select(ApprovalDecisionModel).where(
            ApprovalDecisionModel.organization_id == organization_id,
            ApprovalDecisionModel.request_id == request_id,
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    # -------------------------------------------------------------------------
    # Comments
    # -------------------------------------------------------------------------

    async def create_comment(
        self,
        organization_id: uuid.UUID,
        approval_request_id: uuid.UUID,
        author_id: uuid.UUID,
        comment: str,
    ) -> ApprovalCommentModel:
        """Append an immutable review comment."""
        comm = ApprovalCommentModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            approval_request_id=approval_request_id,
            author_id=author_id,
            comment=comment,
        )
        self.session.add(comm)
        await self.session.flush()
        return comm

    async def get_comments_for_request(
        self, organization_id: uuid.UUID, approval_request_id: uuid.UUID
    ) -> list[ApprovalCommentModel]:
        """Fetch comments for a request in chronological order."""
        stmt = (
            select(ApprovalCommentModel)
            .where(
                ApprovalCommentModel.organization_id == organization_id,
                ApprovalCommentModel.approval_request_id == approval_request_id,
            )
            .order_by(ApprovalCommentModel.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

"""Review comment and reviewer revision tracking service."""

import logging
import uuid

from app.governance.domain.models import ApprovalComment
from app.governance.infrastructure.repository import GovernanceRepository

logger = logging.getLogger(__name__)


class ReviewService:
    """Manages immutable reviewer feedback and discussion threads on approval requests."""

    def __init__(self, repository: GovernanceRepository) -> None:
        self.repo = repository

    async def add_comment(
        self,
        organization_id: uuid.UUID,
        request_id: uuid.UUID,
        author_id: uuid.UUID,
        comment: str,
    ) -> ApprovalComment:
        """Append an immutable review comment."""
        clean_comment = comment.strip()
        if not clean_comment:
            raise ValueError("Review comment cannot be empty")

        record = await self.repo.create_comment(
            organization_id=organization_id,
            approval_request_id=request_id,
            author_id=author_id,
            comment=clean_comment,
        )
        return ApprovalComment(
            id=record.id,
            approval_request_id=record.approval_request_id,
            organization_id=record.organization_id,
            author_id=record.author_id,
            comment=record.comment,
            created_at=record.created_at,
        )

    async def list_comments(
        self, organization_id: uuid.UUID, request_id: uuid.UUID
    ) -> list[ApprovalComment]:
        """Fetch chronological comments for an approval request."""
        records = await self.repo.get_comments_for_request(organization_id, request_id)
        return [
            ApprovalComment(
                id=r.id,
                approval_request_id=r.approval_request_id,
                organization_id=r.organization_id,
                author_id=r.author_id,
                comment=r.comment,
                created_at=r.created_at,
            )
            for r in records
        ]

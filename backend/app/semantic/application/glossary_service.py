"""Application service managing Business Glossary definitions and version histories."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semantic import BusinessTerm
from app.semantic.domain.enums import SemanticStatus
from app.semantic.domain.errors import SemanticObjectNotFoundError
from app.semantic.infrastructure.repository import SemanticRepository


class GlossaryService:
    """Coordinates business glossary term creation, versioning, review, and search."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SemanticRepository(session)

    async def create_term(
        self,
        organization_id: uuid.UUID,
        name: str,
        definition: str,
        description: str | None = None,
        category: str | None = None,
        owner: str | None = None,
        steward: str | None = None,
        created_by: uuid.UUID | None = None,
    ) -> BusinessTerm:
        """Create a new draft business term."""
        return await self.repo.create_term(
            organization_id=organization_id,
            name=name,
            definition=definition,
            description=description,
            category=category,
            owner=owner,
            steward=steward,
            created_by=created_by,
            status=SemanticStatus.DRAFT,
        )

    async def update_term(
        self,
        term_id: uuid.UUID,
        organization_id: uuid.UUID,
        definition: str | None = None,
        description: str | None = None,
        category: str | None = None,
        owner: str | None = None,
        steward: str | None = None,
        updated_by: uuid.UUID | None = None,
    ) -> BusinessTerm:
        """Update existing business term definition, recording an immutable version."""
        return await self.repo.update_term(
            term_id=term_id,
            organization_id=organization_id,
            definition=definition,
            description=description,
            category=category,
            owner=owner,
            steward=steward,
            updated_by=updated_by,
        )

    async def get_term(self, term_id: uuid.UUID, organization_id: uuid.UUID) -> BusinessTerm:
        term = await self.repo.get_term(term_id, organization_id)
        if not term:
            raise SemanticObjectNotFoundError("term", term_id)
        return term

    async def list_terms(
        self,
        organization_id: uuid.UUID,
        status: SemanticStatus | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[BusinessTerm]:
        return await self.repo.list_terms(
            organization_id=organization_id,
            status=status,
            category=category,
            offset=offset,
            limit=limit,
        )

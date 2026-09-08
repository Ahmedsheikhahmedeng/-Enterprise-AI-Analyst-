"""Conflict detection service uncovering contradictory formulas and colliding definitions."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semantic import SemanticConflict, SemanticMetric
from app.semantic.domain.enums import ConflictSeverity
from app.semantic.infrastructure.repository import SemanticRepository


class SemanticConflictDetector:
    """Discovers semantic discrepancies and duplicate conceptual assertions within an organization."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SemanticRepository(session)

    async def detect_metric_conflicts(self, organization_id: uuid.UUID) -> list[SemanticConflict]:
        """Scan all metrics in an organization to detect identical names with divergent formulas."""
        stmt = select(SemanticMetric).where(SemanticMetric.organization_id == organization_id)
        res = await self.session.execute(stmt)
        metrics = list(res.scalars().all())

        # Group metrics by normalized name
        by_norm_name: dict[str, list[SemanticMetric]] = {}
        for m in metrics:
            by_norm_name.setdefault(m.normalized_name, []).append(m)

        detected_conflicts: list[SemanticConflict] = []

        for norm_name, group in by_norm_name.items():
            if len(group) > 1:
                # Check if formulas differ
                formulas = {m.formula.strip().lower() for m in group}
                if len(formulas) > 1:
                    conflict = await self.repo.create_conflict(
                        organization_id=organization_id,
                        object_type="metric",
                        object_ids=[str(m.id) for m in group],
                        reason=(
                            f"Contradictory formulas detected for metric '{norm_name}': "
                            f"{list(formulas)}"
                        ),
                        severity=ConflictSeverity.HIGH,
                    )
                    detected_conflicts.append(conflict)

        return detected_conflicts

    async def list_unresolved_conflicts(self, organization_id: uuid.UUID) -> list[SemanticConflict]:
        return await self.repo.list_conflicts(organization_id, unresolved_only=True)

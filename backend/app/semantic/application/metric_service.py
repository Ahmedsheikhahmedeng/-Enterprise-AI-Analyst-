"""Application service managing Semantic Metrics and formula validation."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semantic import SemanticMetric
from app.semantic.application.metric_compiler import MetricCompiler
from app.semantic.domain.enums import SemanticStatus
from app.semantic.domain.errors import SemanticObjectNotFoundError
from app.semantic.infrastructure.repository import SemanticRepository


class MetricService:
    """Coordinates lifecycle and formula integrity for semantic metrics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SemanticRepository(session)

    async def create_metric(
        self,
        organization_id: uuid.UUID,
        name: str,
        definition: str,
        formula: str,
        aggregation: str,
        display_name: str | None = None,
        description: str | None = None,
        grain: str | None = None,
        filters: list[str] | None = None,
        unit: str | None = None,
        dataset_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
    ) -> SemanticMetric:
        # Validate formula against security AST / injection boundaries
        MetricCompiler.validate_formula(formula)
        if filters:
            for f in filters:
                MetricCompiler.validate_formula(f)

        return await self.repo.create_metric(
            organization_id=organization_id,
            name=name,
            definition=definition,
            formula=formula,
            aggregation=aggregation,
            display_name=display_name,
            description=description,
            grain=grain,
            filters=filters,
            unit=unit,
            dataset_id=dataset_id,
            created_by=created_by,
            status=SemanticStatus.DRAFT,
        )

    async def get_metric(self, metric_id: uuid.UUID, organization_id: uuid.UUID) -> SemanticMetric:
        metric = await self.repo.get_metric(metric_id, organization_id)
        if not metric:
            raise SemanticObjectNotFoundError("metric", metric_id)
        return metric

    async def list_metrics(
        self,
        organization_id: uuid.UUID,
        status: SemanticStatus | None = None,
        dataset_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[SemanticMetric]:
        return await self.repo.list_metrics(
            organization_id=organization_id,
            status=status,
            dataset_id=dataset_id,
            offset=offset,
            limit=limit,
        )

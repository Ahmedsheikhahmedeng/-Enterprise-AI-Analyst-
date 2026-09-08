"""Protocol contracts for Semantic Layer storage, search, and compilation."""

import uuid
from typing import Any, Protocol

from app.semantic.domain.models import (
    MetricDefinition,
    SemanticSearchResultItem,
)


class SemanticRepository(Protocol):
    """Protocol for persisting and retrieving tenant-isolated semantic objects."""

    async def get_term(self, term_id: uuid.UUID, organization_id: uuid.UUID) -> Any | None: ...

    async def get_metric(self, metric_id: uuid.UUID, organization_id: uuid.UUID) -> Any | None: ...

    async def get_dimension(
        self, dimension_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Any | None: ...

    async def get_entity(self, entity_id: uuid.UUID, organization_id: uuid.UUID) -> Any | None: ...


class SemanticSearchProvider(Protocol):
    """Protocol for multi-modal semantic discovery across concepts."""

    async def search(
        self,
        query: str,
        organization_id: uuid.UUID,
        limit: int = 10,
        object_types: list[str] | None = None,
        only_published: bool = True,
    ) -> list[SemanticSearchResultItem]: ...


class MetricSQLCompiler(Protocol):
    """Protocol for compiling high-level metric definitions into secure SQL fragments."""

    def compile_metric(
        self,
        definition: MetricDefinition,
        table_name: str,
        column_mapping: dict[str, str],
    ) -> str: ...

"""Domain package for Semantic Catalog and Semantic Layer."""

from app.semantic.domain.enums import (
    ConflictSeverity,
    MappingType,
    MatchSource,
    MetricAggregation,
    RelationshipType,
    SemanticObjectType,
    SemanticStatus,
)
from app.semantic.domain.errors import (
    InvalidMetricFormulaError,
    SemanticConflictError,
    SemanticError,
    SemanticObjectNotFoundError,
    UnauthorizedSemanticActionError,
    UnverifiedSemanticObjectError,
)
from app.semantic.domain.models import (
    ColumnMappingItem,
    MetricDefinition,
    ResolvedDimension,
    ResolvedMetric,
    SemanticConflictModel,
    SemanticQueryPlan,
    SemanticSearchResultItem,
)
from app.semantic.domain.protocols import (
    MetricSQLCompiler,
    SemanticRepository,
    SemanticSearchProvider,
)

__all__ = [
    "SemanticStatus",
    "MetricAggregation",
    "RelationshipType",
    "MappingType",
    "ConflictSeverity",
    "SemanticObjectType",
    "MatchSource",
    "MetricDefinition",
    "ColumnMappingItem",
    "ResolvedMetric",
    "ResolvedDimension",
    "SemanticQueryPlan",
    "SemanticSearchResultItem",
    "SemanticConflictModel",
    "SemanticRepository",
    "SemanticSearchProvider",
    "MetricSQLCompiler",
    "SemanticError",
    "SemanticObjectNotFoundError",
    "SemanticConflictError",
    "InvalidMetricFormulaError",
    "UnauthorizedSemanticActionError",
    "UnverifiedSemanticObjectError",
]

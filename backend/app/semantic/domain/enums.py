"""Enumerations for Semantic Catalog, Metrics, Dimensions, Lifecycle, and Relationships."""

from enum import StrEnum


class SemanticStatus(StrEnum):
    """Publishing lifecycle states for semantic concepts."""

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class MetricAggregation(StrEnum):
    """Mathematical aggregation functions applied by semantic metrics."""

    SUM = "SUM"
    COUNT = "COUNT"
    COUNT_DISTINCT = "COUNT_DISTINCT"
    AVG = "AVG"
    MIN = "MIN"
    MAX = "MAX"
    MEDIAN = "MEDIAN"
    CUSTOM = "CUSTOM"


class RelationshipType(StrEnum):
    """Entity cardinality and join semantics."""

    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"


class MappingType(StrEnum):
    """Strategy by which a semantic concept binds to a physical column."""

    DIRECT = "DIRECT"
    CALCULATED = "CALCULATED"
    FOREIGN_KEY = "FOREIGN_KEY"


class ConflictSeverity(StrEnum):
    """Severity classification for semantic collisions or contradictory formulas."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SemanticObjectType(StrEnum):
    """Types of first-class semantic catalog entities."""

    TERM = "term"
    METRIC = "metric"
    DIMENSION = "dimension"
    ENTITY = "entity"


class MatchSource(StrEnum):
    """Origin of semantic resolution or search hit."""

    EXACT = "exact"
    SYNONYM = "synonym"
    LEXICAL = "lexical"
    VECTOR = "vector"
    VERIFIED_MAPPING = "verified_mapping"

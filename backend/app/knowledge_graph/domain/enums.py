"""Controlled enumeration types for Knowledge Graph nodes, edges, states, and resolution."""

from enum import Enum, StrEnum


class GraphNodeType(StrEnum):
    """Categorization of entities and semantic abstractions in the knowledge graph."""

    ENTITY = "ENTITY"
    TERM = "TERM"
    METRIC = "METRIC"
    DIMENSION = "DIMENSION"
    DATASET = "DATASET"
    DATASET_COLUMN = "DATASET_COLUMN"
    DOCUMENT = "DOCUMENT"


class GraphEdgeType(StrEnum):
    """Strictly controlled relationships connecting knowledge graph nodes."""

    HAS_COLUMN = "HAS_COLUMN"
    MAPS_TO = "MAPS_TO"
    DERIVED_FROM = "DERIVED_FROM"
    BELONGS_TO = "BELONGS_TO"
    RELATES_TO = "RELATES_TO"
    JOINS_WITH = "JOINS_WITH"
    MEASURED_BY = "MEASURED_BY"
    DEFINED_BY = "DEFINED_BY"
    SYNONYM_OF = "SYNONYM_OF"
    LOCATED_IN = "LOCATED_IN"
    PART_OF = "PART_OF"


class RelationshipConfidenceTier(float, Enum):
    """Base confidence scores depending on provenance tier."""

    VERIFIED = 1.0
    EXPLICIT = 0.9
    INFERRED = 0.6


class GraphStatus(StrEnum):
    """Lifecycle stages for knowledge graph nodes and edges."""

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ResolutionStatus(StrEnum):
    """Outcomes of entity identification and resolution against the graph."""

    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


class ConflictSeverity(StrEnum):
    """Severity ratings for knowledge graph collisions or contradictory edges."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConflictStatus(StrEnum):
    """Lifecycle status of a detected graph conflict."""

    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class LineageDirection(StrEnum):
    """Direction of lineage graph traversal."""

    FORWARD = "FORWARD"
    REVERSE = "REVERSE"

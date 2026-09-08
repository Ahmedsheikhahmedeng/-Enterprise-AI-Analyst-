"""Pydantic request and response schemas for Knowledge Graph REST APIs."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GraphNodeResponse(BaseModel):
    """Schema representing a knowledge graph vertex."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    node_type: str
    name: str
    normalized_name: str
    source_object_type: str
    source_object_id: uuid.UUID
    version: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class GraphEdgeResponse(BaseModel):
    """Schema representing a knowledge graph relationship."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    edge_type: str
    weight: float
    confidence: float
    is_verified: bool
    status: str
    source_object_type: str | None = None
    source_object_id: uuid.UUID | None = None
    version: int


class GraphSearchRequest(BaseModel):
    """Input payload for searching nodes in the graph."""

    query: str = Field(..., min_length=1, max_length=500)
    node_type: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class GraphSearchResponse(BaseModel):
    """Results returned from graph node search."""

    nodes: list[GraphNodeResponse]
    count: int


class GraphNeighborsResponse(BaseModel):
    """1-to-4 hop neighbor topology around a node."""

    root_node_id: uuid.UUID
    depth: int
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


class GraphPathItemResponse(BaseModel):
    """A single traversed multi-hop path."""

    depth: int
    confidence: float
    verified_ratio: float
    nodes: list[str]
    edges: list[str]


class GraphPathsRequest(BaseModel):
    """Payload to find paths between two nodes."""

    start_node_id: uuid.UUID
    target_node_id: uuid.UUID
    max_depth: int = Field(default=4, ge=1, le=4)
    max_paths: int = Field(default=10, ge=1, le=50)
    only_verified: bool = False


class GraphPathsResponse(BaseModel):
    """Ranked paths connecting two nodes."""

    paths: list[GraphPathItemResponse]
    count: int


class GraphQueryRequest(BaseModel):
    """Payload for natural language or concept reasoning query."""

    start_entity: str | None = None
    target_concept: str | None = None
    max_depth: int = Field(default=3, ge=1, le=4)


class GraphQueryResponse(BaseModel):
    """Reasoning result with paths, confidence, and provenance."""

    confidence: float
    paths: list[GraphPathItemResponse]
    provenance: dict[str, Any]
    resolved_entities: list[dict[str, Any]] = Field(default_factory=list)


class GraphLineageResponse(BaseModel):
    """Lineage trace output."""

    root_node_id: uuid.UUID
    direction: str
    lineage_paths: list[dict[str, Any]]
    nodes_count: int


class GraphConflictResponse(BaseModel):
    """Graph structural collision or conflicting relationship."""

    id: uuid.UUID
    reason: str
    severity: str
    node_ids: list[str]
    edge_ids: list[str]
    status: str
    created_at: datetime | None = None


class GraphEdgeCreateRequest(BaseModel):
    """Payload to create a directed edge."""

    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    edge_type: str = Field(..., description="Controlled GraphEdgeType")
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    is_verified: bool = False


class GraphEdgeUpdateRequest(BaseModel):
    """Payload to update edge weight or status."""

    weight: float | None = Field(default=None, ge=0.0, le=10.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: str | None = None


class GraphSyncResponse(BaseModel):
    """Summary of semantic synchronization to graph."""

    nodes_created: int
    edges_created: int
    aliases_created: int
    skipped: int

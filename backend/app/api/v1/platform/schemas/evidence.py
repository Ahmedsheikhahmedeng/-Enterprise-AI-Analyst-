"""Citation, Evidence and Provenance Schemas — TASK 34."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CitationItem(BaseModel):
    """Frontend-ready citation contract enabling interactive source inspection."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Citation symbol matching response anchor, e.g. 'S1', 'R2'")
    source_type: str = Field(..., description="Source origin: 'SQL', 'RAG', 'GRAPH', 'SEMANTIC'")
    title: str = Field(..., description="Human-readable title or entity/table name")
    snippet: str = Field(..., description="Sanitized excerpt or query outcome")
    trust: str = Field(
        "DIRECT", description="Trust classification: 'DIRECT', 'DERIVED', 'HYPOTHESIS'"
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score for this citation")


class EvidenceItem(BaseModel):
    """Detailed evidence unit collected during execution."""

    model_config = ConfigDict(extra="ignore")

    citation_id: str = Field(..., description="Associated citation identifier")
    source_type: str = Field(..., description="Source category")
    source_id: str | None = Field(None, description="Internal non-sensitive reference ID")
    title: str = Field(..., description="Display title")
    snippet: str = Field(..., description="Evidence text or data snippet")
    trust_level: str = Field("DIRECT", description="Trust level")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict, description="Safe auxiliary metadata")


class ProvenanceResponse(BaseModel):
    """Full reasoning lineage, DAG nodes, and evidence provenance."""

    model_config = ConfigDict(extra="ignore")

    execution_id: uuid.UUID = Field(..., description="Execution UUID")
    mode: str = Field("AUTO", description="Execution mode")
    strategy: str = Field("HYBRID", description="Reasoning strategy")
    stages: list[dict[str, Any]] = Field(
        default_factory=list, description="Reasoning execution stages"
    )
    citations: list[CitationItem] = Field(
        default_factory=list, description="All verified citations"
    )
    diagnostics: dict[str, Any] = Field(
        default_factory=dict, description="Performance and latency diagnostics"
    )

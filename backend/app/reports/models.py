"""Domain models representing structured report documents, findings, and metadata."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ReportStatus(StrEnum):
    """Lifecycle states of an enterprise analytical report."""

    DRAFT = "draft"
    GENERATED = "generated"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    FAILED = "failed"


@dataclass
class KeyFinding:
    """Individual analytical conclusion grounded in evidence."""

    id: str
    title: str
    statement: str
    importance: str = "medium"  # high, medium, low
    citations: list[str] = field(default_factory=list)
    numeric_values: list[float] = field(default_factory=list)


@dataclass
class ReportMetric:
    """Structured numeric or categorical indicator extracted from SQL analysis."""

    name: str
    value: Any
    unit: str | None = None
    period: str | None = None
    source: str = "S1"
    description: str | None = None


@dataclass
class ReportTable:
    """Tabular dataset excerpt extracted from structured analysis for reporting."""

    id: str
    title: str
    columns: list[str]
    rows: list[list[Any]]
    source_refs: list[str] = field(default_factory=list)


@dataclass
class ChartSpec:
    """Declarative specification for data visualization."""

    id: str
    type: str  # bar, line, pie, area, table
    title: str
    x_axis: str
    y_axis: str
    series: list[dict[str, Any]]
    source_refs: list[str] = field(default_factory=list)


@dataclass
class ReportEvidence:
    """Unified evidence marker preserving provenance from Task 18."""

    id: str  # S1, S2, R1, R2...
    type: str  # sql or document
    title: str
    is_calculated: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportConflict:
    """Disclosed contradiction between SQL data and unstructured documents."""

    field: str
    source_a: str
    value_a: Any
    source_b: str
    value_b: Any
    severity: str
    description: str


@dataclass
class ReportSection:
    """Additional modular narrative section within the report."""

    id: str
    title: str
    content: str
    order: int = 0


@dataclass
class ReportDocument:
    """Canonical domain representation of an Enterprise Analytical Report."""

    report_id: UUID
    organization_id: UUID
    title: str
    status: ReportStatus
    version: int
    created_at: datetime
    updated_at: datetime
    executive_summary: str
    analysis_run_id: UUID | None = None
    subtitle: str | None = None
    created_by: UUID | None = None
    published_at: datetime | None = None
    sections: list[ReportSection] = field(default_factory=list)
    key_findings: list[KeyFinding] = field(default_factory=list)
    metrics: list[ReportMetric] = field(default_factory=list)
    tables: list[ReportTable] = field(default_factory=list)
    charts: list[ChartSpec] = field(default_factory=list)
    evidence: list[ReportEvidence] = field(default_factory=list)
    conflicts: list[ReportConflict] = field(default_factory=list)
    methodology: str = ""
    data_sources: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    prompt_version: str = "1.0.0"
    generator_version: str = "1.0.0"
    template_version: str = "1.0.0"
    content_hash: str = ""
    language: str = "en"  # "en", "ar", "tr"
    direction: str = "ltr"  # "ltr", "rtl"

    def to_dict(self) -> dict[str, Any]:
        """Serialize domain model to JSON-compatible dictionary."""
        data = asdict(self)
        data["report_id"] = str(self.report_id)
        data["organization_id"] = str(self.organization_id)
        data["analysis_run_id"] = str(self.analysis_run_id) if self.analysis_run_id else None
        data["created_by"] = str(self.created_by) if self.created_by else None
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        data["published_at"] = self.published_at.isoformat() if self.published_at else None
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReportDocument":
        """Reconstruct domain model from serialized dictionary."""
        return cls(
            report_id=UUID(data["report_id"]),
            organization_id=UUID(data["organization_id"]),
            analysis_run_id=UUID(data["analysis_run_id"]) if data.get("analysis_run_id") else None,
            title=data["title"],
            subtitle=data.get("subtitle"),
            status=ReportStatus(data["status"]),
            version=int(data.get("version", 1)),
            created_by=UUID(data["created_by"]) if data.get("created_by") else None,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            published_at=(
                datetime.fromisoformat(data["published_at"]) if data.get("published_at") else None
            ),
            executive_summary=data["executive_summary"],
            sections=[ReportSection(**sec) for sec in data.get("sections", [])],
            key_findings=[KeyFinding(**kf) for kf in data.get("key_findings", [])],
            metrics=[ReportMetric(**m) for m in data.get("metrics", [])],
            tables=[ReportTable(**t) for t in data.get("tables", [])],
            charts=[ChartSpec(**c) for c in data.get("charts", [])],
            evidence=[ReportEvidence(**ev) for ev in data.get("evidence", [])],
            conflicts=[ReportConflict(**cf) for cf in data.get("conflicts", [])],
            methodology=data.get("methodology", ""),
            data_sources=data.get("data_sources", []),
            diagnostics=data.get("diagnostics", {}),
            prompt_version=data.get("prompt_version", "1.0.0"),
            generator_version=data.get("generator_version", "1.0.0"),
            template_version=data.get("template_version", "1.0.0"),
            content_hash=data.get("content_hash", ""),
            language=data.get("language", "en"),
            direction=data.get("direction", "ltr"),
        )

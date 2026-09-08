"""End-to-end evidence collection and provenance tracking for agent outputs."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class EvidenceItem:
    """Individual grounded piece of evidence discovered during tool execution."""

    evidence_id: str  # e.g., 'S1', 'R1', 'REP-1'
    source_type: str  # 'sql', 'rag', 'report', 'evaluation'
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ProvenanceTracker:
    """Collects and organizes evidence references produced during tool execution."""

    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        self._evidence_map: dict[str, EvidenceItem] = {}
        self._tool_usage: list[str] = []

    def record_evidence(self, item: EvidenceItem) -> None:
        """Register newly verified evidence."""
        self._evidence_map[item.evidence_id] = item

    def record_tool(self, tool_name: str) -> None:
        """Record usage of a tool."""
        if tool_name not in self._tool_usage:
            self._tool_usage.append(tool_name)

    def get_citations(self) -> list[str]:
        """Return list of distinct evidence IDs collected."""
        return list(self._evidence_map.keys())

    def get_all_evidence(self) -> list[EvidenceItem]:
        """Return full collection of evidence."""
        return list(self._evidence_map.values())

    def get_tools_used(self) -> list[str]:
        """Return distinct tools invoked."""
        return list(self._tool_usage)

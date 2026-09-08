"""MarkdownRenderer: Produces clean, standardized GitHub-Flavored Markdown reports."""

from typing import Any

from app.reports.models import ReportDocument
from app.reports.renderers.base import BaseReportRenderer


class MarkdownRenderer(BaseReportRenderer):
    """Renders ReportDocument into deterministic, cleanly formatted Markdown."""

    def render(self, doc: ReportDocument, **kwargs: Any) -> str:
        """Serialize report to Markdown document."""
        lines: list[str] = []

        # 1. Title Header
        lines.append(f"# {doc.title}")
        if doc.subtitle:
            lines.append(f"*{doc.subtitle}*")
        lines.append("")

        # 2. Executive Summary
        lines.append("## Executive Summary")
        lines.append(doc.executive_summary)
        lines.append("")

        # 3. Key Findings
        if doc.key_findings:
            lines.append("## Key Findings")
            for f in doc.key_findings:
                cit_str = " ".join(f"[{c}]" for c in f.citations) if f.citations else ""
                lines.append(f"- **{f.title}**: {f.statement} {cit_str}".strip())
            lines.append("")

        # 4. Metrics Table
        if doc.metrics:
            lines.append("## Key Metrics")
            lines.append("| Metric | Value | Source |")
            lines.append("| :--- | :--- | :--- |")
            for m in doc.metrics:
                unit_str = f" {m.unit}" if m.unit else ""
                lines.append(f"| {m.name} | {m.value}{unit_str} | [{m.source}] |")
            lines.append("")

        # 5. Data Tables
        if doc.tables:
            for table in doc.tables:
                lines.append(f"## {table.title}")
                # Table header
                header_line = "| " + " | ".join(table.columns) + " |"
                sep_line = "| " + " | ".join([":---"] * len(table.columns)) + " |"
                lines.append(header_line)
                lines.append(sep_line)
                # Rows
                for row in table.rows:
                    row_str = (
                        "| "
                        + " | ".join(str(cell) if cell is not None else "-" for cell in row)
                        + " |"
                    )
                    lines.append(row_str)
                lines.append("")

        # 6. Data Conflicts Section
        if doc.conflicts:
            lines.append("## Data Conflicts & Discrepancies")
            lines.append("> [!WARNING]")
            lines.append(
                "> Contradictions between structured databases and document sources were detected:"
            )
            lines.append("")
            lines.append("| Metric / Field | Source A | Value A | Source B | Value B | Severity |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for c in doc.conflicts:
                row_str = (
                    f"| {c.field} | {c.source_a} | {c.value_a} | "
                    f"{c.source_b} | {c.value_b} | {c.severity.upper()} |"
                )
                lines.append(row_str)
            lines.append("")

        # 7. Data Sources & Provenance
        if doc.data_sources:
            lines.append("## Data Sources & Provenance")
            for src in doc.data_sources:
                lines.append(f"- {src}")
            lines.append("")

        # 8. Methodology
        if doc.methodology:
            lines.append("## Methodology")
            lines.append(doc.methodology)
            lines.append("")

        # 9. Audit Metadata Footer
        lines.append("---")
        lines.append("### Metadata & Audit")
        lines.append(f"- **Report ID**: `{doc.report_id}`")
        lines.append(f"- **Version**: `v{doc.version}` ({doc.status.value.upper()})")
        lines.append(f"- **Content Hash**: `{doc.content_hash}`")
        lines.append(f"- **Generated At**: `{doc.created_at.isoformat()}`")
        if doc.published_at:
            lines.append(f"- **Published At**: `{doc.published_at.isoformat()}`")

        return "\n".join(lines).strip()

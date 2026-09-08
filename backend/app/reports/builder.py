import contextlib
import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.reports.config import ReportConfig, get_report_config
from app.reports.models import (
    ChartSpec,
    KeyFinding,
    ReportConflict,
    ReportDocument,
    ReportEvidence,
    ReportMetric,
    ReportStatus,
    ReportTable,
)


class ReportBuilder:
    """Transforms raw AI Analyst execution results into a comprehensive ReportDocument."""

    def __init__(self, config: ReportConfig | None = None) -> None:
        self.config = config or get_report_config()

    def build_from_analysis_context(
        self,
        *,
        title: str,
        organization_id: UUID,
        analysis_run_id: UUID | None = None,
        user_id: UUID | None = None,
        subtitle: str | None = None,
        query: str = "",
        answer: str = "",
        confidence: float = 1.0,
        evidence_list: list[dict[str, Any]] | None = None,
        conflicts_list: list[dict[str, Any]] | None = None,
        citations_list: list[dict[str, Any]] | None = None,
        diagnostics: dict[str, Any] | None = None,
        sql_rows: list[dict[str, Any]] | None = None,
        sql_metrics: dict[str, Any] | None = None,
        template: str = "executive",
        version: int = 1,
        status: ReportStatus = ReportStatus.DRAFT,
    ) -> ReportDocument:
        """Construct a validated ReportDocument from raw analytical components."""
        evidence_list = evidence_list or []
        conflicts_list = conflicts_list or []
        citations_list = citations_list or []
        diagnostics = diagnostics or {}
        sql_rows = sql_rows or []
        sql_metrics = sql_metrics or {}

        # 1. Detect language and text direction
        combined_text = f"{title} {query} {answer}"
        language, direction = self._detect_language_and_direction(combined_text)

        # 2. Build normalized evidence models
        evidence_models = self._build_evidence_models(evidence_list, citations_list)

        # 3. Build conflicts
        conflict_models = self._build_conflict_models(conflicts_list)

        # 4. Extract structured metrics (SQL metrics prioritized)
        metric_models = self._extract_metrics(sql_metrics, sql_rows, evidence_models)

        # 5. Extract tables
        table_models = self._extract_tables(sql_rows)

        # 6. Build chart specifications
        chart_models = self._build_charts(table_models, metric_models)

        # 7. Extract Key Findings from answer & evidence
        findings = self._extract_key_findings(answer, evidence_models)

        # 8. Executive Summary
        exec_summary = answer.strip()
        if not exec_summary:
            exec_summary = (
                "No substantive analytical evidence available to generate an executive summary."
            )

        # 9. Methodology
        methodology = (
            "This enterprise intelligence report was synthesized using deterministic "
            "query routing, read-only structured SQL execution over authorized relational "
            "schemas, hybrid dense-sparse document retrieval, cross-encoder reranking, "
            "and citation grounding validation."
        )

        # 10. Data sources (sanitized without credentials)
        data_sources = self._collect_data_sources(evidence_models)

        now = datetime.now(UTC)
        doc = ReportDocument(
            report_id=uuid4(),
            organization_id=organization_id,
            analysis_run_id=analysis_run_id,
            created_by=user_id,
            title=title.strip(),
            subtitle=subtitle.strip() if subtitle else None,
            status=status,
            version=version,
            created_at=now,
            updated_at=now,
            published_at=now if status == ReportStatus.PUBLISHED else None,
            executive_summary=exec_summary,
            sections=[],
            key_findings=findings,
            metrics=metric_models,
            tables=table_models,
            charts=chart_models,
            evidence=evidence_models,
            conflicts=conflict_models,
            methodology=methodology,
            data_sources=data_sources,
            diagnostics=diagnostics,
            prompt_version=self.config.prompt_version,
            generator_version=self.config.generator_version,
            template_version=template,
            language=language,
            direction=direction,
        )

        # Compute deterministic content hash
        doc.content_hash = self.compute_content_hash(doc)
        return doc

    def compute_content_hash(self, doc: ReportDocument) -> str:
        """Compute SHA-256 fingerprint across all substantive analytical elements."""
        hasher = hashlib.sha256()
        canonical_dict = {
            "title": doc.title,
            "executive_summary": doc.executive_summary,
            "findings": [
                {"id": f.id, "statement": f.statement, "citations": sorted(f.citations)}
                for f in doc.key_findings
            ],
            "metrics": [
                {"name": m.name, "value": str(m.value), "source": m.source} for m in doc.metrics
            ],
            "tables": [
                {"title": t.title, "columns": t.columns, "row_count": len(t.rows)}
                for t in doc.tables
            ],
            "evidence": [{"id": e.id, "type": e.type, "title": e.title} for e in doc.evidence],
            "conflicts": [
                {"field": c.field, "a": str(c.value_a), "b": str(c.value_b)} for c in doc.conflicts
            ],
        }
        encoded = json.dumps(canonical_dict, sort_keys=True).encode("utf-8")
        hasher.update(encoded)
        return hasher.hexdigest()

    def _build_evidence_models(
        self,
        raw_evidence: list[dict[str, Any]],
        citations: list[dict[str, Any]],
    ) -> list[ReportEvidence]:
        """Normalize raw evidence dictionary objects into ReportEvidence items."""
        models: list[ReportEvidence] = []
        seen_ids: set[str] = set()

        for ev in raw_evidence:
            ev_id = ev.get("evidence_id") or ev.get("id")
            if not ev_id or ev_id in seen_ids:
                continue
            seen_ids.add(ev_id)

            metadata = ev.get("metadata") or {}
            # Sanitize metadata to remove any potential connection strings or secrets
            clean_meta = {
                k: v
                for k, v in metadata.items()
                if not any(
                    secret in k.lower() for secret in ["password", "secret", "conn", "key", "token"]
                )
            }

            models.append(
                ReportEvidence(
                    id=ev_id,
                    type=ev.get("source_type") or ("sql" if ev_id.startswith("S") else "document"),
                    title=ev.get("title")
                    or (
                        f"SQL Analysis [{ev_id}]"
                        if ev_id.startswith("S")
                        else f"Document Source [{ev_id}]"
                    ),
                    is_calculated=bool(ev.get("is_calculated", ev_id.startswith("S"))),
                    metadata=clean_meta,
                )
            )

        # Also incorporate any cited IDs from citations list if not present
        for cit in citations:
            cit_id = cit.get("id")
            if cit_id and cit_id not in seen_ids:
                seen_ids.add(cit_id)
                models.append(
                    ReportEvidence(
                        id=cit_id,
                        type=cit.get("type", "document"),
                        title=cit.get("title", f"Source {cit_id}"),
                        is_calculated=bool(cit.get("is_calculated", False)),
                        metadata={},
                    )
                )

        return sorted(models, key=lambda x: (x.id[0], int(x.id[1:]) if x.id[1:].isdigit() else 0))

    def _build_conflict_models(
        self,
        raw_conflicts: list[dict[str, Any]],
    ) -> list[ReportConflict]:
        """Convert conflict dictionaries into ReportConflict domain instances."""
        conflicts: list[ReportConflict] = []
        for c in raw_conflicts:
            conflicts.append(
                ReportConflict(
                    field=str(c.get("field", "value")),
                    source_a=str(c.get("source_a", "Structured SQL")),
                    value_a=c.get("value_a"),
                    source_b=str(c.get("source_b", "Document Source")),
                    value_b=c.get("value_b"),
                    severity=str(c.get("severity", "medium")),
                    description=str(c.get("description", "Discrepancy observed between sources")),
                )
            )
        return conflicts

    def _extract_metrics(
        self,
        sql_metrics: dict[str, Any],
        sql_rows: list[dict[str, Any]],
        evidence: list[ReportEvidence],
    ) -> list[ReportMetric]:
        """Extract structured numeric metrics, prioritizing structured SQL metrics."""
        metrics: list[ReportMetric] = []
        sql_source = "S1"
        for ev in evidence:
            if ev.type == "sql":
                sql_source = ev.id
                break

        # 1. From sql_metrics dictionary
        for k, v in sql_metrics.items():
            if len(metrics) >= self.config.max_metrics:
                break
            clean_name = k.replace("_", " ").title()
            metrics.append(
                ReportMetric(
                    name=clean_name,
                    value=v,
                    source=sql_source,
                )
            )

        # 2. From first row numeric aggregations if metrics dictionary was sparse
        if not metrics and sql_rows:
            first_row = sql_rows[0]
            for col_name, val in first_row.items():
                if isinstance(val, (int, float)) and len(metrics) < self.config.max_metrics:
                    metrics.append(
                        ReportMetric(
                            name=col_name.replace("_", " ").title(),
                            value=val,
                            source=sql_source,
                        )
                    )

        return metrics

    def _extract_tables(self, sql_rows: list[dict[str, Any]]) -> list[ReportTable]:
        """Convert SQL row dictionaries into ReportTable models."""
        if not sql_rows:
            return []

        columns = list(sql_rows[0].keys())
        bounded_rows = sql_rows[: self.config.max_table_rows]
        matrix = [[row.get(col) for col in columns] for row in bounded_rows]

        return [
            ReportTable(
                id="T1",
                title="Structured Analysis Data",
                columns=columns,
                rows=matrix,
                source_refs=["S1"],
            )
        ]

    def _build_charts(
        self,
        tables: list[ReportTable],
        metrics: list[ReportMetric],
    ) -> list[ChartSpec]:
        """Construct declarative ChartSpec models from tabular or metric values."""
        charts: list[ChartSpec] = []
        if not tables:
            # Fallback: Bar chart from numeric metrics if at least 2 metrics exist
            numeric_metrics = [m for m in metrics if isinstance(m.value, (int, float))]
            if len(numeric_metrics) >= 2:
                charts.append(
                    ChartSpec(
                        id="C1",
                        type="bar",
                        title="Key Metrics Comparison",
                        x_axis="Metric",
                        y_axis="Value",
                        series=[
                            {
                                "name": "Value",
                                "values": [m.value for m in numeric_metrics],
                                "labels": [m.name for m in numeric_metrics],
                            }
                        ],
                        source_refs=["S1"],
                    )
                )
            return charts

        # Extract chart from primary table
        table = tables[0]
        if len(table.columns) >= 2 and len(table.rows) >= 2:
            x_col = table.columns[0]
            # Look for numeric y columns
            numeric_col_indices = [
                i
                for i in range(1, len(table.columns))
                if any(isinstance(row[i], (int, float)) for row in table.rows if row[i] is not None)
            ]
            if numeric_col_indices:
                y_idx = numeric_col_indices[0]
                y_col = table.columns[y_idx]

                y_title = y_col.replace("_", " ").title()
                x_title = x_col.replace("_", " ").title()
                charts.append(
                    ChartSpec(
                        id="C1",
                        type="bar",
                        title=f"{y_title} by {x_title}",
                        x_axis=x_col,
                        y_axis=y_col,
                        series=[
                            {
                                "name": y_col,
                                "labels": [str(row[0]) for row in table.rows],
                                "values": [row[y_idx] for row in table.rows],
                            }
                        ],
                        source_refs=table.source_refs,
                    )
                )

        return charts

    def _extract_key_findings(
        self,
        answer: str,
        evidence: list[ReportEvidence],
    ) -> list[KeyFinding]:
        """Extract numbered key findings attributing them with evidence citations."""
        findings: list[KeyFinding] = []
        if not answer:
            return findings

        # Split answer into paragraphs or substantial sentences
        raw_parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", answer) if p.strip()]

        citation_re = re.compile(r"\[([SRE]\d+)\]")
        number_re = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?%?")

        all_ev_ids = {e.id for e in evidence}
        default_citation = next(iter(all_ev_ids)) if all_ev_ids else ""

        for idx, part in enumerate(raw_parts, start=1):
            if len(findings) >= self.config.max_findings:
                break
            if len(part) < 10:
                continue

            found_citations = citation_re.findall(part)
            valid_citations = [c for c in found_citations if c in all_ev_ids]

            # If no citation in sentence, attribute to first valid evidence if available
            if not valid_citations and default_citation:
                valid_citations = [default_citation]

            # Extract numbers
            raw_nums = number_re.findall(part)
            numeric_vals: list[float] = []
            for n in raw_nums:
                clean_n = n.replace("%", "").replace(",", "")
                with contextlib.suppress(ValueError):
                    numeric_vals.append(float(clean_n))

            # Title summary
            clean_statement = part
            title = part[:60].strip() + ("..." if len(part) > 60 else "")

            findings.append(
                KeyFinding(
                    id=f"F{idx}",
                    title=title,
                    statement=clean_statement,
                    importance="high" if idx == 1 else "medium",
                    citations=valid_citations,
                    numeric_values=numeric_vals,
                )
            )

        return findings

    def _collect_data_sources(self, evidence: list[ReportEvidence]) -> list[str]:
        """Extract clean, redacted names of data sources used in the report."""
        sources: list[str] = []
        for ev in evidence:
            label = f"[{ev.id}] {ev.title} ({'Structured SQL' if ev.is_calculated else 'Document'})"
            if label not in sources:
                sources.append(label)
        return sources

    def _detect_language_and_direction(self, text: str) -> tuple[str, str]:
        """Detect whether text is predominantly Arabic, Turkish, or English."""
        # Check Arabic unicode range
        arabic_chars = len(re.findall(r"[\u0600-\u06FF]", text))
        if arabic_chars > 5:
            return "ar", "rtl"

        # Check Turkish specific characters
        turkish_chars = len(re.findall(r"[çğıöşüÇĞİÖŞÜ]", text))
        if turkish_chars > 2:
            return "tr", "ltr"

        return "en", "ltr"

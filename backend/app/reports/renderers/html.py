"""HTMLRenderer: Produces standalone, responsive, print-ready semantic HTML5 reports."""

import html
from typing import Any

from app.reports.models import ReportDocument
from app.reports.renderers.base import BaseReportRenderer


class HTMLRenderer(BaseReportRenderer):
    """Renders ReportDocument into secure, self-contained semantic HTML with CSS."""

    def render(self, doc: ReportDocument, **kwargs: Any) -> str:
        """Serialize report to standalone HTML string."""
        direction = "rtl" if doc.direction == "rtl" else "ltr"
        lang = doc.language or ("ar" if direction == "rtl" else "en")

        title_esc = html.escape(doc.title)
        subtitle_esc = html.escape(doc.subtitle or "")
        summary_esc = html.escape(doc.executive_summary)
        methodology_esc = html.escape(doc.methodology)

        # Build Findings HTML
        findings_html = ""
        if doc.key_findings:
            findings_items = []
            for f in doc.key_findings:
                cits = " ".join(
                    f'<span class="badge badge-source">[{html.escape(c)}]</span>'
                    for c in f.citations
                )
                f_title = html.escape(f.title)
                f_stmt = html.escape(f.statement)
                findings_items.append(
                    f'<li class="finding-item"><strong>{f_title}</strong>: {f_stmt} {cits}</li>'
                )
            findings_html = (
                f'<section class="card">'
                f"<h2>Key Findings</h2>"
                f'<ul class="findings-list">{"".join(findings_items)}</ul>'
                f"</section>"
            )

        # Build Metrics HTML
        metrics_html = ""
        if doc.metrics:
            metric_cards = []
            for m in doc.metrics:
                m_name = html.escape(m.name)
                m_val = html.escape(str(m.value))
                m_unit = f" {html.escape(m.unit)}" if m.unit else ""
                m_src = html.escape(m.source)
                metric_cards.append(
                    f'<div class="metric-card">'
                    f'<div class="metric-title">{m_name}</div>'
                    f'<div class="metric-value">{m_val}{m_unit}</div>'
                    f'<div class="metric-source">Source: <span class="badge">[{m_src}]</span></div>'
                    f"</div>"
                )
            metrics_html = (
                f'<section class="card">'
                f"<h2>Key Metrics</h2>"
                f'<div class="metrics-grid">{"".join(metric_cards)}</div>'
                f"</section>"
            )

        # Build Tables HTML
        tables_html = ""
        if doc.tables:
            table_blocks = []
            for t in doc.tables:
                t_title = html.escape(t.title)
                headers = "".join(f"<th>{html.escape(col)}</th>" for col in t.columns)
                rows_html = []
                for row in t.rows:
                    cells = "".join(
                        f"<td>{html.escape(str(c) if c is not None else '-')}</td>" for c in row
                    )
                    rows_html.append(f"<tr>{cells}</tr>")
                table_blocks.append(
                    f'<div class="table-container">'
                    f"<h3>{t_title}</h3>"
                    f'<table class="data-table">'
                    f"<thead><tr>{headers}</tr></thead>"
                    f"<tbody>{''.join(rows_html)}</tbody>"
                    f"</table>"
                    f"</div>"
                )
            tables_html = (
                f'<section class="card"><h2>Structured Data</h2>{"".join(table_blocks)}</section>'
            )

        # Build Conflicts HTML
        conflicts_html = ""
        if doc.conflicts:
            c_rows = []
            for c in doc.conflicts:
                val_a = html.escape(str(c.value_a))
                val_b = html.escape(str(c.value_b))
                sev = html.escape(c.severity.upper())
                c_rows.append(
                    f"<tr>"
                    f"<td>{html.escape(c.field)}</td>"
                    f"<td>{html.escape(c.source_a)}: <strong>{val_a}</strong></td>"
                    f"<td>{html.escape(c.source_b)}: <strong>{val_b}</strong></td>"
                    f'<td><span class="badge badge-warning">{sev}</span></td>'
                    f"</tr>"
                )
            warn_msg = (
                "The following contradictions between structured and "
                "unstructured sources were verified:"
            )
            th_row = "<tr><th>Field</th><th>Source A</th><th>Source B</th><th>Severity</th></tr>"
            conflicts_html = (
                f'<section class="card conflict-card">'
                f"<h2>Data Discrepancies & Conflicts</h2>"
                f'<p class="warning-text">{warn_msg}</p>'
                f'<table class="data-table">'
                f"<thead>{th_row}</thead>"
                f"<tbody>{''.join(c_rows)}</tbody>"
                f"</table>"
                f"</section>"
            )

        # Build Data Sources HTML
        sources_html = ""
        if doc.data_sources:
            s_items = "".join(f"<li>{html.escape(src)}</li>" for src in doc.data_sources)
            sources_html = (
                f'<section class="card">'
                f"<h2>Data Sources & Provenance</h2>"
                f'<ul class="sources-list">{s_items}</ul>'
                f"</section>"
            )

        # Base CSS styles (Self-contained, responsive, print-friendly)
        css = """
        :root {
            --bg-color: #f8fafc;
            --surface-color: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border-color: #e2e8f0;
            --primary: #2563eb;
            --warning-bg: #fffbeb;
            --warning-border: #fef08a;
            --warning-text: #854d0e;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.6;
            padding: 2rem;
        }
        .container { max-width: 960px; margin: 0 auto; }
        header {
            margin-bottom: 2rem;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 1.5rem;
        }
        h1 {
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-main);
            margin-bottom: 0.5rem;
        }
        .subtitle {
            font-size: 1.1rem;
            color: var(--text-muted);
            font-style: italic;
            margin-bottom: 0.5rem;
        }
        .meta-bar {
            font-size: 0.875rem;
            color: var(--text-muted);
            display: flex;
            gap: 1.5rem;
            flex-wrap: wrap;
        }
        .card {
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        h2 {
            font-size: 1.25rem;
            margin-bottom: 1rem;
            color: var(--primary);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.5rem;
        }
        h3 { font-size: 1rem; margin: 1rem 0 0.5rem 0; color: var(--text-main); }
        .findings-list, .sources-list { padding-inline-start: 1.5rem; }
        .finding-item { margin-bottom: 0.75rem; }
        .badge {
            display: inline-block;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
            background: #e0e7ff;
            color: #3730a3;
        }
        .badge-warning { background: #fef3c7; color: #92400e; }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 1rem;
        }
        .metric-card {
            background: #f1f5f9;
            padding: 1rem;
            border-radius: 6px;
            border: 1px solid #cbd5e1;
        }
        .metric-title {
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
        }
        .metric-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-main);
            margin: 0.25rem 0;
        }
        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
            margin-top: 0.5rem;
        }
        .data-table th, .data-table td {
            border: 1px solid var(--border-color);
            padding: 0.6rem 0.8rem;
            text-align: start;
        }
        .data-table th { background: #f8fafc; font-weight: 600; }
        .conflict-card { background: var(--warning-bg); border-color: var(--warning-border); }
        .warning-text { color: var(--warning-text); font-size: 0.9rem; margin-bottom: 0.75rem; }
        footer {
            margin-top: 3rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border-color);
            font-size: 0.8rem;
            color: var(--text-muted);
        }
        @media print {
            body { background: #fff; padding: 0; }
            .card { box-shadow: none; border: 1px solid #ccc; break-inside: avoid; }
        }
        """

        gen_time = doc.created_at.strftime("%Y-%m-%d %H:%M UTC")
        methodology_section = (
            f'<section class="card"><h2>Methodology</h2><p>{methodology_esc}</p></section>'
            if methodology_esc
            else ""
        )
        subtitle_tag = f'<div class="subtitle">{subtitle_esc}</div>' if subtitle_esc else ""

        return f"""<!DOCTYPE html>
<html dir="{direction}" lang="{lang}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title_esc}</title>
    <style>{css}</style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{title_esc}</h1>
            {subtitle_tag}
            <div class="meta-bar">
                <span><strong>Version:</strong> v{doc.version} ({doc.status.value.upper()})</span>
                <span><strong>Generated:</strong> {gen_time}</span>
                <span><strong>Hash:</strong> <code>{doc.content_hash[:16]}...</code></span>
            </div>
        </header>

        <section class="card">
            <h2>Executive Summary</h2>
            <p>{summary_esc}</p>
        </section>

        {findings_html}
        {metrics_html}
        {tables_html}
        {conflicts_html}
        {sources_html}

        {methodology_section}

        <footer>
            <p>Enterprise AI Analyst &mdash; Report ID: {doc.report_id}
            &bull; Hash: {doc.content_hash}</p>
        </footer>
    </div>
</body>
</html>"""

"""PDFRenderer: Produces deterministic, A4 paginated PDF reports using ReportLab."""

import io
import os
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.reports.models import ReportDocument
from app.reports.renderers.base import BaseReportRenderer


class NumberedCanvas(canvas.Canvas):  # type: ignore[misc]
    """Two-pass canvas recording total page count and rendering consistent headers/footers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Footer
        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(A4[0] - 36, 20, footer_text)
        self.drawString(36, 20, "Enterprise AI Analyst — Confidential & Proprietary")

        # Header (pages after first)
        if self._pageNumber > 1:
            self.drawString(36, A4[1] - 25, "Enterprise Analytical Report")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, A4[1] - 28, A4[0] - 36, A4[1] - 28)

        self.restoreState()


class PDFRenderer(BaseReportRenderer):
    """Generates print-quality, deterministic A4 PDF reports."""

    _font_initialized: bool = False
    _active_font: str = "Helvetica"
    _active_bold_font: str = "Helvetica-Bold"

    @classmethod
    def _init_fonts(cls) -> None:
        """Attempt to register a TrueType font for rich Unicode support if available."""
        if cls._font_initialized:
            return
        cls._font_initialized = True

        candidate_fonts = [
            ("/System/Library/Fonts/Supplemental/Arial.ttf", "SystemArial"),
            ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "ArialUnicode"),
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans"),
        ]
        for path, name in candidate_fonts:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    cls._active_font = name
                    cls._active_bold_font = name
                    break
                except Exception:
                    pass

    def render(self, doc: ReportDocument, **kwargs: Any) -> bytes:
        """Build and serialize ReportDocument into PDF bytes."""
        self._init_fonts()
        buffer = io.BytesIO()

        pdf_doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        font_name = self._active_font
        bold_font = self._active_bold_font

        # Style definitions
        title_style = ParagraphStyle(
            "ReportTitle",
            fontName=bold_font,
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            fontName=font_name,
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=8,
        )
        meta_style = ParagraphStyle(
            "ReportMeta",
            fontName=font_name,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#64748B"),
        )
        heading_style = ParagraphStyle(
            "ReportH2",
            fontName=bold_font,
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#1E3A8A"),
            spaceBefore=12,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "ReportBody",
            fontName=font_name,
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor("#334155"),
            spaceAfter=6,
        )
        finding_style = ParagraphStyle(
            "ReportFinding",
            fontName=font_name,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#1E293B"),
            spaceAfter=4,
        )
        table_cell_style = ParagraphStyle(
            "TableCell",
            fontName=font_name,
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#0F172A"),
        )
        table_header_style = ParagraphStyle(
            "TableHeader",
            fontName=bold_font,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#0F172A"),
        )

        elements: list[Any] = []

        # 1. Header Title Block
        elements.append(Paragraph(doc.title, title_style))
        if doc.subtitle:
            elements.append(Paragraph(doc.subtitle, subtitle_style))

        meta_line = (
            f"<b>Version:</b> v{doc.version} ({doc.status.value.upper()}) &nbsp;&bull;&nbsp; "
            f"<b>Generated:</b> {doc.created_at.strftime('%Y-%m-%d %H:%M UTC')} &nbsp;&bull;&nbsp; "
            f"<b>Hash:</b> {doc.content_hash[:16]}..."
        )
        elements.append(Paragraph(meta_line, meta_style))
        elements.append(Spacer(1, 10))
        elements.append(
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=12)
        )

        # 2. Executive Summary
        elements.append(Paragraph("Executive Summary", heading_style))
        elements.append(Paragraph(doc.executive_summary, body_style))
        elements.append(Spacer(1, 8))

        # 3. Key Findings
        if doc.key_findings:
            elements.append(Paragraph("Key Findings", heading_style))
            for f in doc.key_findings:
                cit_text = " ".join(f"<b>[{c}]</b>" for c in f.citations)
                f_text = f"&bull; <b>{f.title}</b>: {f.statement} {cit_text}"
                elements.append(Paragraph(f_text, finding_style))
            elements.append(Spacer(1, 8))

        # 4. Key Metrics Table
        if doc.metrics:
            elements.append(Paragraph("Key Metrics", heading_style))
            metric_data = [
                [
                    Paragraph("<b>Metric</b>", table_header_style),
                    Paragraph("<b>Value</b>", table_header_style),
                    Paragraph("<b>Source</b>", table_header_style),
                ]
            ]
            for m in doc.metrics:
                unit = f" {m.unit}" if m.unit else ""
                metric_data.append(
                    [
                        Paragraph(m.name, table_cell_style),
                        Paragraph(f"{m.value}{unit}", table_cell_style),
                        Paragraph(f"[{m.source}]", table_cell_style),
                    ]
                )
            t_metrics = Table(metric_data, colWidths=[200, 200, 100])
            t_metrics.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            elements.append(t_metrics)
            elements.append(Spacer(1, 8))

        # 5. Data Tables
        if doc.tables:
            for tbl in doc.tables:
                elements.append(Paragraph(tbl.title, heading_style))
                table_matrix = [
                    [Paragraph(f"<b>{col}</b>", table_header_style) for col in tbl.columns]
                ]
                for row in tbl.rows:
                    table_matrix.append(
                        [
                            Paragraph(str(cell) if cell is not None else "-", table_cell_style)
                            for cell in row
                        ]
                    )

                col_w = min(500 // max(len(tbl.columns), 1), 150)
                col_widths = [col_w] * len(tbl.columns)
                t_grid = Table(table_matrix, colWidths=col_widths)
                t_grid.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                elements.append(KeepTogether([t_grid]))
                elements.append(Spacer(1, 8))

        # 6. Data Conflicts
        if doc.conflicts:
            elements.append(Paragraph("Data Conflicts & Discrepancies", heading_style))
            conflict_data = [
                [
                    Paragraph("<b>Field</b>", table_header_style),
                    Paragraph("<b>Source A</b>", table_header_style),
                    Paragraph("<b>Source B</b>", table_header_style),
                    Paragraph("<b>Severity</b>", table_header_style),
                ]
            ]
            for c in doc.conflicts:
                conflict_data.append(
                    [
                        Paragraph(c.field, table_cell_style),
                        Paragraph(f"{c.source_a}: {c.value_a}", table_cell_style),
                        Paragraph(f"{c.source_b}: {c.value_b}", table_cell_style),
                        Paragraph(c.severity.upper(), table_cell_style),
                    ]
                )
            t_conflicts = Table(conflict_data, colWidths=[120, 160, 160, 60])
            t_conflicts.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FEF3C7")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FDE68A")),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            elements.append(KeepTogether([t_conflicts]))
            elements.append(Spacer(1, 8))

        # 7. Data Sources & Provenance
        if doc.data_sources:
            elements.append(Paragraph("Data Sources & Provenance", heading_style))
            for src in doc.data_sources:
                elements.append(Paragraph(f"&bull; {src}", body_style))
            elements.append(Spacer(1, 8))

        # 8. Methodology
        if doc.methodology:
            elements.append(Paragraph("Methodology", heading_style))
            elements.append(Paragraph(doc.methodology, body_style))
            elements.append(Spacer(1, 8))

        # Build PDF with two-pass NumberedCanvas
        pdf_doc.build(elements, canvasmaker=NumberedCanvas)
        return buffer.getvalue()

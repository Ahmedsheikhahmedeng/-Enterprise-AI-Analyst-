"""Unit tests for enterprise report builder, validation, versioning, renderers, and security."""

import io
import uuid
from datetime import UTC, datetime

import pytest
from pypdf import PdfReader

from app.reports.builder import ReportBuilder
from app.reports.exceptions import (
    ReportValidationError,
)
from app.reports.exporters.csv import CSVExporter
from app.reports.models import (
    KeyFinding,
    ReportConflict,
    ReportDocument,
    ReportEvidence,
    ReportMetric,
    ReportStatus,
    ReportTable,
)
from app.reports.policies import ReportSecurityPolicy
from app.reports.renderers.html import HTMLRenderer
from app.reports.renderers.markdown import MarkdownRenderer
from app.reports.renderers.pdf import PDFRenderer
from app.reports.validator import ReportValidator


class TestReportBuilder:
    """Validates ReportBuilder conversion logic across all analytical modalities."""

    @pytest.fixture
    def builder(self) -> ReportBuilder:
        return ReportBuilder()

    def test_sql_only_report_construction(self, builder: ReportBuilder) -> None:
        """Verify building report from structured SQL analysis context."""
        org_id = uuid.uuid4()
        doc = builder.build_from_analysis_context(
            title="Q4 Revenue Analysis",
            organization_id=org_id,
            query="What was total revenue in Q4?",
            answer="Q4 revenue was $120,000,000.00 [S1].",
            evidence_list=[
                {
                    "evidence_id": "S1",
                    "source_type": "sql",
                    "title": "sales_db",
                    "is_calculated": True,
                    "metadata": {"row_count": 1},
                }
            ],
            sql_metrics={"total_revenue": 120000000.0},
            sql_rows=[{"quarter": "Q4", "revenue": 120000000.0}],
        )

        assert doc.title == "Q4 Revenue Analysis"
        assert doc.organization_id == org_id
        assert len(doc.metrics) >= 1
        assert doc.metrics[0].name == "Total Revenue"
        assert doc.metrics[0].value == 120000000.0
        assert len(doc.tables) == 1
        assert doc.tables[0].columns == ["quarter", "revenue"]
        assert len(doc.evidence) == 1
        assert doc.evidence[0].id == "S1"
        assert len(doc.key_findings) >= 1
        assert "S1" in doc.key_findings[0].citations
        assert doc.content_hash != ""

    def test_rag_only_report_construction(self, builder: ReportBuilder) -> None:
        """Verify building report from document-based unstructured retrieval."""
        org_id = uuid.uuid4()
        doc = builder.build_from_analysis_context(
            title="Policy Review Report",
            organization_id=org_id,
            query="What is the travel expense policy?",
            answer="All business travel expenses must be pre-approved by a director [R1].",
            evidence_list=[
                {
                    "evidence_id": "R1",
                    "source_type": "document",
                    "title": "Expense Policy 2025",
                    "is_calculated": False,
                    "metadata": {"page": 3},
                }
            ],
        )

        assert doc.title == "Policy Review Report"
        assert len(doc.evidence) == 1
        assert doc.evidence[0].id == "R1"
        assert len(doc.tables) == 0
        assert len(doc.key_findings) >= 1
        assert "R1" in doc.key_findings[0].citations

    def test_hybrid_report_construction_with_conflicts(self, builder: ReportBuilder) -> None:
        """Verify building report with both structured data, documents, and discrepancies."""
        org_id = uuid.uuid4()
        doc = builder.build_from_analysis_context(
            title="Revenue Reconciliation Report",
            organization_id=org_id,
            query="What was revenue and what did management state?",
            answer=(
                "Q4 revenue calculated at $120,000,000.00 [S1]. "
                "The annual report stated revenue reached $126,000,000.00 [R1]."
            ),
            evidence_list=[
                {
                    "evidence_id": "S1",
                    "source_type": "sql",
                    "title": "sales",
                    "is_calculated": True,
                },
                {
                    "evidence_id": "R1",
                    "source_type": "document",
                    "title": "Annual Report",
                    "is_calculated": False,
                },
            ],
            conflicts_list=[
                {
                    "field": "revenue",
                    "source_a": "sales database",
                    "value_a": 120000000.0,
                    "source_b": "annual report",
                    "value_b": 126000000.0,
                    "severity": "medium",
                    "description": "5% discrepancy noted",
                }
            ],
            sql_rows=[{"period": "Q4", "revenue": 120000000.0}],
            sql_metrics={"q4_revenue": 120000000.0},
        )

        assert len(doc.evidence) == 2
        assert len(doc.conflicts) == 1
        assert doc.conflicts[0].severity == "medium"
        assert len(doc.tables) == 1
        assert len(doc.metrics) >= 1

    def test_empty_evidence_fallback(self, builder: ReportBuilder) -> None:
        """Verify safe handling when no analytical evidence exists."""
        org_id = uuid.uuid4()
        doc = builder.build_from_analysis_context(
            title="Empty Report",
            organization_id=org_id,
            answer="",
            evidence_list=[],
        )
        assert "No substantive analytical evidence available" in doc.executive_summary
        assert len(doc.key_findings) == 0


class TestReportValidator:
    """Validates structural constraints, citation grounding, and anti-hallucination rules."""

    @pytest.fixture
    def validator(self) -> ReportValidator:
        return ReportValidator()

    def test_valid_report_passes(self, validator: ReportValidator) -> None:
        """Ensure properly attributed report passes validation."""
        now = datetime.now(UTC)
        doc = ReportDocument(
            report_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            title="Valid Executive Report",
            status=ReportStatus.DRAFT,
            version=1,
            created_at=now,
            updated_at=now,
            executive_summary="Summary text [S1].",
            evidence=[ReportEvidence(id="S1", type="sql", title="sales", is_calculated=True)],
            key_findings=[
                KeyFinding(
                    id="F1",
                    title="Revenue",
                    statement="Revenue grew [S1]",
                    citations=["S1"],
                )
            ],
        )
        # Should not raise
        validator.validate(doc)

    def test_phantom_citation_rejected(self, validator: ReportValidator) -> None:
        """Ensure citations to non-existent evidence IDs raise ReportValidationError."""
        now = datetime.now(UTC)
        doc = ReportDocument(
            report_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            title="Phantom Citation Report",
            status=ReportStatus.DRAFT,
            version=1,
            created_at=now,
            updated_at=now,
            executive_summary="Summary text [S1].",
            evidence=[ReportEvidence(id="S1", type="sql", title="sales", is_calculated=True)],
            key_findings=[
                KeyFinding(id="F1", title="Claim", statement="Factual claim", citations=["R99"])
            ],
        )
        with pytest.raises(ReportValidationError) as exc_info:
            validator.validate(doc)
        assert "phantom_citation" in exc_info.value.details

    def test_empty_title_rejected(self, validator: ReportValidator) -> None:
        """Ensure empty title is rejected."""
        now = datetime.now(UTC)
        doc = ReportDocument(
            report_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            title="   ",
            status=ReportStatus.DRAFT,
            version=1,
            created_at=now,
            updated_at=now,
            executive_summary="Summary",
        )
        with pytest.raises(ReportValidationError) as exc:
            validator.validate(doc)
        assert exc.value.details["field"] == "title"


class TestReportRenderers:
    """Verifies rendering across Markdown, HTML, PDF, and CSV."""

    @pytest.fixture
    def sample_doc(self) -> ReportDocument:
        now = datetime.now(UTC)
        return ReportDocument(
            report_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            title="Q4 Financial Report",
            subtitle="Executive Performance Summary",
            status=ReportStatus.DRAFT,
            version=1,
            created_at=now,
            updated_at=now,
            executive_summary="Revenue reached $120M [S1]. Demand was strong [R1].",
            key_findings=[
                KeyFinding(
                    id="F1",
                    title="Revenue Level",
                    statement="Revenue reached $120M",
                    citations=["S1"],
                ),
                KeyFinding(
                    id="F2",
                    title="Market Demand",
                    statement="Strong enterprise demand",
                    citations=["R1"],
                ),
            ],
            metrics=[
                ReportMetric(name="Total Revenue", value=120000000.0, unit="USD", source="S1")
            ],
            tables=[
                ReportTable(
                    id="T1",
                    title="Quarterly Breakdown",
                    columns=["Quarter", "Revenue"],
                    rows=[["Q1", 100], ["Q2", 110], ["Q3", 115], ["Q4", 120]],
                    source_refs=["S1"],
                )
            ],
            conflicts=[
                ReportConflict(
                    field="revenue",
                    source_a="SQL DB",
                    value_a=120,
                    source_b="Report PDF",
                    value_b=125,
                    severity="medium",
                    description="5% difference",
                )
            ],
            evidence=[
                ReportEvidence(id="S1", type="sql", title="sales_db", is_calculated=True),
                ReportEvidence(id="R1", type="document", title="10-K Filing", is_calculated=False),
            ],
            methodology="Standard analytical pipeline.",
            data_sources=["[S1] sales_db", "[R1] 10-K Filing"],
            content_hash="abc123hash",
        )

    def test_markdown_renderer(self, sample_doc: ReportDocument) -> None:
        """Verify Markdown output structure and content."""
        renderer = MarkdownRenderer()
        md = renderer.render(sample_doc)

        assert "# Q4 Financial Report" in md
        assert "## Executive Summary" in md
        assert "## Key Findings" in md
        assert "[S1]" in md
        assert "[R1]" in md
        assert "Quarterly Breakdown" in md
        assert "| Quarter | Revenue |" in md
        assert "Data Conflicts & Discrepancies" in md
        assert "abc123hash" in md

    def test_html_renderer(self, sample_doc: ReportDocument) -> None:
        """Verify HTML output semantic structure, escaping, and styling."""
        renderer = HTMLRenderer()
        html_out = renderer.render(sample_doc)

        assert "<!DOCTYPE html>" in html_out
        assert "<title>Q4 Financial Report</title>" in html_out
        assert "<h2>Executive Summary</h2>" in html_out
        assert "Revenue reached $120M" in html_out
        assert '<table class="data-table">' in html_out
        assert "Data Discrepancies & Conflicts" in html_out
        assert "abc123hash" in html_out

    def test_html_xss_escaping(self) -> None:
        """Verify that malicious input is properly escaped in HTML."""
        now = datetime.now(UTC)
        malicious_doc = ReportDocument(
            report_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            title="<script>alert('pwned')</script>",
            status=ReportStatus.DRAFT,
            version=1,
            created_at=now,
            updated_at=now,
            executive_summary="<img src=x onerror=alert(1)>",
        )
        renderer = HTMLRenderer()
        html_out = renderer.render(malicious_doc)

        assert "<script>" not in html_out
        assert "&lt;script&gt;alert(&#x27;pwned&#x27;)&lt;/script&gt;" in html_out
        assert "<img" not in html_out

    def test_pdf_renderer_via_pypdf(self, sample_doc: ReportDocument) -> None:
        """Verify PDF bytes generation and programmatic inspection via pypdf."""
        renderer = PDFRenderer()
        pdf_bytes = renderer.render(sample_doc)

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 500
        assert pdf_bytes.startswith(b"%PDF-")

        # Programmatic inspection with pypdf
        reader = PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) >= 1
        page_text = reader.pages[0].extract_text()
        assert "Q4 Financial Report" in page_text
        assert "Executive Summary" in page_text
        assert "Key Findings" in page_text
        assert "S1" in page_text

    def test_csv_exporter(self, sample_doc: ReportDocument) -> None:
        """Verify CSV export of structured report tables."""
        exporter = CSVExporter()
        csv_text = exporter.export(sample_doc)

        lines = csv_text.strip().split("\n")
        assert len(lines) >= 5
        assert "Quarter,Revenue" in lines[0]
        assert "Q1,100" in lines[1]
        assert "Q4,120" in lines[4]


class TestReportSecurityPolicy:
    """Verifies filename sanitization and directory traversal prevention."""

    def test_sanitize_filename_traversal_prevention(self) -> None:
        """Verify directory traversal tokens are stripped."""
        policy = ReportSecurityPolicy()
        safe_name = policy.sanitize_filename(
            title="../../etc/passwd secret report!!",
            version=1,
            ext="pdf",
        )
        assert safe_name == "etcpasswd-secret-report-v1.pdf"
        assert "/" not in safe_name
        assert "\\" not in safe_name
        assert ".." not in safe_name

    def test_sanitize_filename_unsupported_ext_fallback(self) -> None:
        """Verify unsupported extensions fall back to txt."""
        policy = ReportSecurityPolicy()
        safe_name = policy.sanitize_filename(
            title="Audit Report",
            version=2,
            ext="exe",
        )
        assert safe_name.endswith(".txt")

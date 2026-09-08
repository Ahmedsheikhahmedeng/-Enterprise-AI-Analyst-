"""ReportValidator: Enforces structural, citation, numeric, and anti-hallucination rules."""

from app.reports.exceptions import ReportValidationError
from app.reports.models import ReportDocument


class ReportValidator:
    """Validates that a ReportDocument meets integrity and grounding standards."""

    def validate(self, doc: ReportDocument) -> None:
        """Execute full validation suite on ReportDocument,
        raising ReportValidationError on failure.
        """
        self.validate_structure(doc)
        self.validate_citations(doc)
        self.validate_numeric_integrity(doc)
        self.validate_conflicts(doc)

    def validate_structure(self, doc: ReportDocument) -> None:
        """Verify essential structural properties and unique identifiers."""
        if not doc.title or not doc.title.strip():
            raise ReportValidationError(
                message="Report title is required and cannot be empty.",
                details={"field": "title"},
            )

        if not doc.executive_summary or not doc.executive_summary.strip():
            raise ReportValidationError(
                message="Executive summary is required and cannot be empty.",
                details={"field": "executive_summary"},
            )

        if not doc.organization_id:
            raise ReportValidationError(
                message="Report must be scoped to an organization ID.",
                details={"field": "organization_id"},
            )

        # Unique finding IDs
        finding_ids = [f.id for f in doc.key_findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ReportValidationError(
                message="Duplicate KeyFinding identifiers detected.",
                details={"finding_ids": finding_ids},
            )

        # Unique table IDs
        table_ids = [t.id for t in doc.tables]
        if len(table_ids) != len(set(table_ids)):
            raise ReportValidationError(
                message="Duplicate ReportTable identifiers detected.",
                details={"table_ids": table_ids},
            )

    def validate_citations(self, doc: ReportDocument) -> None:
        """Verify that all cited source tags exist within the report's evidence collection."""
        valid_ev_ids = {e.id for e in doc.evidence}

        for finding in doc.key_findings:
            for cit in finding.citations:
                if cit not in valid_ev_ids:
                    raise ReportValidationError(
                        message=f"KeyFinding '{finding.id}' cites non-existent evidence [{cit}].",
                        details={"finding_id": finding.id, "phantom_citation": cit},
                    )

        for table in doc.tables:
            for s_ref in table.source_refs:
                if s_ref not in valid_ev_ids:
                    msg = f"ReportTable '{table.id}' references non-existent evidence [{s_ref}]."
                    raise ReportValidationError(
                        message=msg,
                        details={"table_id": table.id, "phantom_source": s_ref},
                    )

    def validate_numeric_integrity(self, doc: ReportDocument) -> None:
        """Verify metrics and table columns have valid numeric and structural representations."""
        for metric in doc.metrics:
            if metric.value is None or (isinstance(metric.value, str) and not metric.value.strip()):
                raise ReportValidationError(
                    message=f"ReportMetric '{metric.name}' contains empty value.",
                    details={"metric": metric.name},
                )

        for table in doc.tables:
            if not table.columns:
                raise ReportValidationError(
                    message=f"ReportTable '{table.id}' has no defined columns.",
                    details={"table_id": table.id},
                )

    def validate_conflicts(self, doc: ReportDocument) -> None:
        """Ensure conflicts have valid sources and values populated."""
        for c in doc.conflicts:
            if not c.source_a or not c.source_b:
                raise ReportValidationError(
                    message="ReportConflict requires both source_a and source_b to be specified.",
                    details={"field": c.field},
                )

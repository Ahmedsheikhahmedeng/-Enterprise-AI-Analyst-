"""CSVExporter: Safely exports structured ReportTable items to CSV format."""

import csv
import io

from app.reports.exceptions import ReportExportError
from app.reports.models import ReportDocument
from app.security.export_security import sanitize_csv_cell


class CSVExporter:
    """Exports tabular analytical data contained strictly within verified ReportDocuments."""

    def export(self, doc: ReportDocument, table_id: str | None = None) -> str:
        """Serialize report tables to standard CSV format.

        If table_id is specified, exports that table; otherwise exports the first table
        or combines multiple tables with sectional headers.
        Protects against CSV Formula Injection (DDE attacks) via sanitize_csv_cell.
        """
        if not doc.tables:
            if doc.metrics:
                output = io.StringIO()
                writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
                writer.writerow(["Metric", "Value", "Unit", "Period", "Source"])
                for m in doc.metrics:
                    writer.writerow(
                        [
                            sanitize_csv_cell(m.name),
                            sanitize_csv_cell(m.value),
                            sanitize_csv_cell(m.unit or ""),
                            sanitize_csv_cell(m.period or ""),
                            sanitize_csv_cell(m.source or ""),
                        ]
                    )
                return output.getvalue()
            raise ReportExportError(
                message="Report contains no tabular data to export as CSV.",
                details={"report_id": str(doc.report_id)},
            )

        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        target_tables = doc.tables
        if table_id:
            target_tables = [t for t in doc.tables if t.id == table_id]
            if not target_tables:
                raise ReportExportError(
                    message=f"Table with id '{table_id}' not found in report.",
                    details={"table_id": table_id, "available": [t.id for t in doc.tables]},
                )

        for idx, table in enumerate(target_tables):
            if len(target_tables) > 1:
                if idx > 0:
                    writer.writerow([])  # Blank spacer row
                writer.writerow([f"# Table: {sanitize_csv_cell(table.title)} ({table.id})"])

            # Header row
            writer.writerow([sanitize_csv_cell(col) for col in table.columns])

            # Data rows with formula injection neutralization
            for row in table.rows:
                writer.writerow([sanitize_csv_cell(cell) for cell in row])

        return output.getvalue()

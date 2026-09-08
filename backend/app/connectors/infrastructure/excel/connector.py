"""Excel (.xlsx) connector using streaming openpyxl reader with formula injection protection."""

import hashlib
import io
import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import openpyxl

from app.connectors.domain.capabilities import ConnectorCapabilities
from app.connectors.domain.enums import ConnectorType
from app.connectors.domain.errors import (
    FileProcessingError,
    QueryExecutionError,
    SchemaDiscoveryError,
)
from app.connectors.domain.models import (
    ColumnSchema,
    ConnectionTestResult,
    PreviewResult,
    QueryRequest,
    QueryResult,
    SchemaModel,
    TableSchema,
)
from app.connectors.domain.protocols import DataConnector
from app.core.logging import get_logger

logger = get_logger("connectors.excel")

MAX_EXCEL_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_EXCEL_SHEETS = 30
MAX_EXCEL_COLUMNS = 200
MAX_EXCEL_ROWS = 50000
MAX_CELL_LENGTH = 4096

FORMULA_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class ExcelConnector(DataConnector):
    """Data connector for Microsoft Excel (.xlsx) workbooks."""

    def __init__(self) -> None:
        self._capabilities = ConnectorCapabilities(
            schema_read=True,
            query=True,
            write=False,
            sync=True,
            streaming=True,
            cdc=False,
            files=True,
            embedding=False,
        )

    @property
    def capabilities(self) -> ConnectorCapabilities:
        return self._capabilities

    def _sanitize_cell(self, value: Any) -> Any:
        """Neutralize potential spreadsheet formula injection and length limits."""
        if value is None:
            return None
        if isinstance(value, str):
            if len(value) > MAX_CELL_LENGTH:
                value = value[:MAX_CELL_LENGTH]
            if value.startswith(FORMULA_INJECTION_PREFIXES):
                return f"'{value}"
        elif isinstance(value, datetime):
            return value.isoformat()
        return value

    def _get_workbook_source(self, config: dict[str, Any]) -> str | io.BytesIO:
        """Validate and return file path or BytesIO buffer."""
        if "file_bytes" in config and config["file_bytes"]:
            raw_val = config["file_bytes"]
            if isinstance(raw_val, str):
                import base64

                raw_bytes = base64.b64decode(raw_val)
            else:
                raw_bytes = bytes(raw_val)
            if len(raw_bytes) > MAX_EXCEL_FILE_SIZE_BYTES:
                raise FileProcessingError(
                    "inline_excel", "Excel workbook exceeds maximum size bound."
                )
            return io.BytesIO(raw_bytes)

        file_path = config.get("file_path")
        if not file_path:
            raise FileProcessingError(
                "unknown", "Missing 'file_path' or 'file_bytes' in Excel configuration."
            )

        str_path = str(file_path)
        if not os.path.exists(str_path):
            raise FileProcessingError(str_path, "Excel file does not exist.")

        size = os.path.getsize(str_path)
        if size > MAX_EXCEL_FILE_SIZE_BYTES:
            raise FileProcessingError(str_path, f"Excel file size ({size} bytes) exceeds limit.")

        return str_path

    async def test_connection(
        self,
        config: dict[str, Any],
        timeout_seconds: float = 5.0,
    ) -> ConnectionTestResult:
        """Test that the Excel workbook opens and sheets can be discovered."""
        t0 = time.perf_counter()
        wb = None
        try:
            source = self._get_workbook_source(config)
            wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
            sheet_names = wb.sheetnames
            latency_ms = (time.perf_counter() - t0) * 1000
            if not sheet_names:
                return ConnectionTestResult(
                    success=False,
                    latency_ms=latency_ms,
                    message="Excel workbook has no sheets.",
                )
            return ConnectionTestResult(
                success=True,
                latency_ms=latency_ms,
                message=f"Excel workbook verified with {len(sheet_names)} sheets: {', '.join(sheet_names[:5])}",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            return ConnectionTestResult(
                success=False,
                latency_ms=latency_ms,
                message=f"Excel verification failed: {exc}",
            )
        finally:
            if wb:
                wb.close()

    async def get_schema(
        self,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        config: dict[str, Any],
    ) -> SchemaModel:
        """Discover sheets as tables and infer column names and types from header and initial rows."""
        wb = None
        try:
            source = self._get_workbook_source(config)
            wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
            sheet_names = wb.sheetnames[:MAX_EXCEL_SHEETS]

            tables: list[TableSchema] = []
            for sheet_name in sheet_names:
                ws = wb[sheet_name]
                rows_iter = ws.iter_rows(values_only=True)
                header_row = next(rows_iter, None)
                if not header_row:
                    continue

                clean_header = [
                    str(h).strip() if h is not None else f"col_{i + 1}"
                    for i, h in enumerate(header_row[:MAX_EXCEL_COLUMNS])
                ]

                # Read up to 50 sample rows for type inference
                sample_rows: list[tuple[Any, ...]] = []
                for idx, r in enumerate(rows_iter):
                    sample_rows.append(r)
                    if idx >= 50:
                        break

                columns: list[ColumnSchema] = []
                for col_idx, col_name in enumerate(clean_header):
                    col_vals = [
                        r[col_idx]
                        for r in sample_rows
                        if len(r) > col_idx and r[col_idx] is not None
                    ]
                    inferred_type = "string"
                    if col_vals:
                        if all(isinstance(v, int) for v in col_vals):
                            inferred_type = "integer"
                        elif all(isinstance(v, (int, float)) for v in col_vals):
                            inferred_type = "float"
                        elif all(isinstance(v, bool) for v in col_vals):
                            inferred_type = "boolean"
                        elif all(isinstance(v, datetime) for v in col_vals):
                            inferred_type = "datetime"

                    columns.append(
                        ColumnSchema(
                            name=col_name,
                            data_type=inferred_type,
                            nullable=True,
                            primary_key=(col_idx == 0 and "id" in col_name.lower()),
                        )
                    )

                tables.append(
                    TableSchema(
                        name=sheet_name,
                        columns=columns,
                        primary_keys=[columns[0].name]
                        if columns and columns[0].primary_key
                        else [],
                    )
                )

            return SchemaModel(
                datasource_id=datasource_id,
                organization_id=organization_id,
                connector_type=ConnectorType.EXCEL,
                tables=tables,
                discovered_at=datetime.now(UTC),
                version=1,
            )
        except Exception as exc:
            logger.error("Failed discovering Excel schema for %s: %s", datasource_id, exc)
            raise SchemaDiscoveryError(datasource_id, str(exc)) from exc
        finally:
            if wb:
                wb.close()

    async def execute_query(
        self,
        request: QueryRequest,
        config: dict[str, Any],
    ) -> QueryResult:
        """Fetch rows from specified sheet (or active sheet) up to max_rows bound."""
        t0 = time.perf_counter()
        wb = None
        try:
            source = self._get_workbook_source(config)
            wb = openpyxl.load_workbook(source, read_only=True, data_only=False)

            target_sheet = config.get("sheet_name")
            if not target_sheet or target_sheet not in wb.sheetnames:
                target_sheet = wb.sheetnames[0]

            ws = wb[target_sheet]
            rows_iter = ws.iter_rows(values_only=True)
            header_row = next(rows_iter, None)
            if not header_row:
                raise QueryExecutionError(
                    request.datasource_id, f"Sheet '{target_sheet}' is empty."
                )

            clean_headers = [
                str(h).strip() if h is not None else f"col_{i + 1}"
                for i, h in enumerate(header_row[:MAX_EXCEL_COLUMNS])
            ]

            rows: list[dict[str, Any]] = []
            for r in rows_iter:
                if len(rows) >= request.max_rows:
                    break
                row_dict: dict[str, Any] = {}
                for i, h in enumerate(clean_headers):
                    val = r[i] if i < len(r) else None
                    row_dict[h] = self._sanitize_cell(val)
                rows.append(row_dict)

            exec_time_ms = (time.perf_counter() - t0) * 1000
            query_hash = hashlib.sha256(request.query.encode("utf-8")).hexdigest()

            return QueryResult(
                columns=clean_headers,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=exec_time_ms,
                datasource_id=request.datasource_id,
                provenance={
                    "organization_id": str(request.organization_id),
                    "datasource_id": str(request.datasource_id),
                    "connector_type": ConnectorType.EXCEL.value,
                    "target_sheet": target_sheet,
                    "query_hash": query_hash,
                    "row_count": len(rows),
                    "execution_time_ms": exec_time_ms,
                },
            )
        except Exception as exc:
            logger.error("Excel query failed: %s", exc)
            raise QueryExecutionError(request.datasource_id, str(exc), request.query[:100]) from exc
        finally:
            if wb:
                wb.close()

    async def preview_data(
        self,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        config: dict[str, Any],
        target_name: str | None = None,
        max_rows: int = 50,
    ) -> PreviewResult:
        """Return safe bounded preview of a sheet in the workbook."""
        cfg = dict(config)
        if target_name:
            cfg["sheet_name"] = target_name

        schema = await self.get_schema(datasource_id, organization_id, cfg)
        target = target_name or (schema.tables[0].name if schema.tables else "Sheet1")
        target_table = next(
            (t for t in schema.tables if t.name == target),
            schema.tables[0] if schema.tables else None,
        )
        cols = target_table.columns if target_table else []

        query_req = QueryRequest(
            datasource_id=datasource_id,
            organization_id=organization_id,
            query="preview",
            max_rows=min(max_rows, 100),
        )
        res = await self.execute_query(query_req, cfg)

        return PreviewResult(
            datasource_id=datasource_id,
            target_name=target,
            columns=cols,
            rows=res.rows,
            total_rows_estimate=res.row_count,
        )

    async def health_check(self, config: dict[str, Any]) -> bool:
        """Liveness check on workbook."""
        res = await self.test_connection(config, timeout_seconds=2.0)
        return res.success

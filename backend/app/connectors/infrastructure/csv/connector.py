"""CSV file connector with streaming schema inference, preview, and formula injection defense."""

import csv
import hashlib
import io
import os
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

logger = get_logger("connectors.csv")

# Maximum limits to protect memory and execution bounds
MAX_CSV_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_CSV_ROWS = 50000
MAX_CSV_COLUMNS = 200
MAX_CELL_LENGTH = 4096

FORMULA_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class CSVConnector(DataConnector):
    """Data connector for CSV tabular files."""

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
        """Neutralize potential spreadsheet formula injection."""
        if isinstance(value, str):
            if len(value) > MAX_CELL_LENGTH:
                value = value[:MAX_CELL_LENGTH]
            if value.startswith(FORMULA_INJECTION_PREFIXES):
                return f"'{value}"
        return value

    def _infer_type(self, values: list[str]) -> str:
        """Infer basic data type from non-empty string samples."""
        non_empty = [v.strip() for v in values if v and v.strip()]
        if not non_empty:
            return "string"

        # Check integer
        is_int = True
        for v in non_empty:
            try:
                int(v)
            except ValueError:
                is_int = False
                break
        if is_int:
            return "integer"

        # Check float
        is_float = True
        for v in non_empty:
            try:
                float(v)
            except ValueError:
                is_float = False
                break
        if is_float:
            return "float"

        # Check boolean
        bool_words = {"true", "false", "yes", "no", "1", "0"}
        if all(v.lower() in bool_words for v in non_empty):
            return "boolean"

        # Check date / datetime
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2})?$")
        if all(date_pattern.match(v) for v in non_empty):
            return "datetime"

        return "string"

    def _get_file_stream(self, config: dict[str, Any]) -> io.TextIOWrapper | io.StringIO:
        """Open CSV file path or wrap in-memory text payload."""
        if "file_content" in config and config["file_content"]:
            raw_text = str(config["file_content"])
            if len(raw_text.encode("utf-8")) > MAX_CSV_FILE_SIZE_BYTES:
                raise FileProcessingError("inline_csv", "CSV payload exceeds maximum size bound.")
            return io.StringIO(raw_text)

        file_path = config.get("file_path")
        if not file_path:
            raise FileProcessingError(
                "unknown", "Missing 'file_path' or 'file_content' in CSV configuration."
            )

        if not os.path.exists(file_path):
            raise FileProcessingError(file_path, "File does not exist.")

        size = os.path.getsize(file_path)
        if size > MAX_CSV_FILE_SIZE_BYTES:
            raise FileProcessingError(file_path, f"CSV file size ({size} bytes) exceeds limit.")

        return open(file_path, encoding=config.get("encoding", "utf-8"), errors="replace")

    async def test_connection(
        self,
        config: dict[str, Any],
        timeout_seconds: float = 5.0,
    ) -> ConnectionTestResult:
        """Verify CSV file exists and is parsable."""
        t0 = time.perf_counter()
        stream = None
        try:
            stream = self._get_file_stream(config)
            reader = csv.reader(stream)
            header = next(reader, None)
            latency_ms = (time.perf_counter() - t0) * 1000
            if header is None:
                return ConnectionTestResult(
                    success=False,
                    latency_ms=latency_ms,
                    message="CSV file is empty.",
                )
            return ConnectionTestResult(
                success=True,
                latency_ms=latency_ms,
                message=f"CSV file verified with {len(header)} columns.",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            return ConnectionTestResult(
                success=False,
                latency_ms=latency_ms,
                message=f"CSV verification failed: {exc}",
            )
        finally:
            if stream and hasattr(stream, "close"):
                stream.close()

    async def get_schema(
        self,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        config: dict[str, Any],
    ) -> SchemaModel:
        """Infer column names and types by inspecting CSV header and sample rows."""
        stream = None
        try:
            stream = self._get_file_stream(config)
            reader = csv.reader(stream)
            header = next(reader, None)
            if not header:
                raise SchemaDiscoveryError(datasource_id, "CSV file is empty or has no header.")

            if len(header) > MAX_CSV_COLUMNS:
                raise SchemaDiscoveryError(
                    datasource_id, f"CSV columns ({len(header)}) exceeds limit ({MAX_CSV_COLUMNS})."
                )

            # Sample rows for type inference
            sample_rows: list[list[str]] = []
            for i, row in enumerate(reader):
                sample_rows.append(row)
                if i >= 100:
                    break

            columns: list[ColumnSchema] = []
            for col_idx, raw_col_name in enumerate(header):
                clean_name = raw_col_name.strip() or f"col_{col_idx + 1}"
                col_values = [r[col_idx] for r in sample_rows if len(r) > col_idx]
                inferred_type = self._infer_type(col_values)
                columns.append(
                    ColumnSchema(
                        name=clean_name,
                        data_type=inferred_type,
                        nullable=True,
                        primary_key=(col_idx == 0 and "id" in clean_name.lower()),
                    )
                )

            file_path = config.get("file_path")
            file_stem = Path(str(file_path)).stem if file_path else "csv_data"
            table_name = config.get("table_name") or file_stem or "csv_data"
            table_schema = TableSchema(
                name=table_name,
                columns=columns,
                primary_keys=[columns[0].name] if columns and columns[0].primary_key else [],
            )

            return SchemaModel(
                datasource_id=datasource_id,
                organization_id=organization_id,
                connector_type=ConnectorType.CSV,
                tables=[table_schema],
                discovered_at=datetime.now(UTC),
                version=1,
            )
        except Exception as exc:
            logger.error("Failed discovering CSV schema for %s: %s", datasource_id, exc)
            raise SchemaDiscoveryError(datasource_id, str(exc)) from exc
        finally:
            if stream and hasattr(stream, "close"):
                stream.close()

    async def execute_query(
        self,
        request: QueryRequest,
        config: dict[str, Any],
    ) -> QueryResult:
        """Filter and fetch rows from CSV based on simple column filters or full read."""
        t0 = time.perf_counter()
        stream = None
        try:
            stream = self._get_file_stream(config)
            reader = csv.reader(stream)
            header = next(reader, None)
            if not header:
                raise QueryExecutionError(request.datasource_id, "CSV is empty.")

            clean_headers = [h.strip() or f"col_{i + 1}" for i, h in enumerate(header)]

            rows: list[dict[str, Any]] = []
            for row in reader:
                if len(rows) >= request.max_rows:
                    break
                row_dict: dict[str, Any] = {}
                for i, h in enumerate(clean_headers):
                    val = row[i] if i < len(row) else None
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
                    "connector_type": ConnectorType.CSV.value,
                    "query_hash": query_hash,
                    "row_count": len(rows),
                    "execution_time_ms": exec_time_ms,
                },
            )
        except Exception as exc:
            logger.error("CSV query failed: %s", exc)
            raise QueryExecutionError(request.datasource_id, str(exc), request.query[:100]) from exc
        finally:
            if stream and hasattr(stream, "close"):
                stream.close()

    async def preview_data(
        self,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        config: dict[str, Any],
        target_name: str | None = None,
        max_rows: int = 50,
    ) -> PreviewResult:
        """Return safe preview sample of CSV records."""
        schema = await self.get_schema(datasource_id, organization_id, config)
        columns = schema.tables[0].columns if schema.tables else []

        query_req = QueryRequest(
            datasource_id=datasource_id,
            organization_id=organization_id,
            query="preview",
            max_rows=min(max_rows, 100),
        )
        res = await self.execute_query(query_req, config)

        return PreviewResult(
            datasource_id=datasource_id,
            target_name=schema.tables[0].name if schema.tables else "csv_data",
            columns=columns,
            rows=res.rows,
            total_rows_estimate=res.row_count,
        )

    async def health_check(self, config: dict[str, Any]) -> bool:
        """Liveness check on CSV asset."""
        res = await self.test_connection(config, timeout_seconds=2.0)
        return res.success

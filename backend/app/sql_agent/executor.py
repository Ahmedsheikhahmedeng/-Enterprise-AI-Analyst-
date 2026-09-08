"""Secure read-only SQL execution engine with timeouts and resource bounding."""

import asyncio
import json
import time
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.sql_agent.config import SQLAgentConfig, get_sql_agent_config
from app.sql_agent.exceptions import (
    SQLResultSizeExceededError,
    SQLTimeoutError,
    SQLValidationError,
)
from app.sql_agent.models import SQLQueryResult

logger = get_logger("sql_agent.executor")


class ReadOnlySQLExecutor:
    """Executes validated read-only SQL statements within strict timeout and memory limits."""

    def __init__(self, config: SQLAgentConfig | None = None) -> None:
        self.config = config or get_sql_agent_config()

    async def execute(
        self,
        sql: str,
        session: AsyncSession,
        params: dict[str, Any] | None = None,
        max_rows: int | None = None,
    ) -> SQLQueryResult:
        """Execute query with read-only transaction parameters and statement timeout."""
        t0 = time.perf_counter()
        statement_timeout_ms = self.config.statement_timeout_ms
        query_timeout_s = self.config.query_timeout_seconds
        eff_max_rows = (
            min(max_rows, self.config.max_rows)
            if max_rows is not None and max_rows > 0
            else self.config.max_rows
        )
        max_bytes = self.config.max_result_bytes

        try:
            async with asyncio.timeout(query_timeout_s):
                # 1. Defense-in-depth: set session-level statement timeout and read-only mode
                await session.execute(
                    text(f"SET LOCAL statement_timeout = {int(statement_timeout_ms)};")
                )
                await session.execute(text("SET LOCAL default_transaction_read_only = on;"))

                # 2. Execute statement with optional bound parameters
                stmt = text(sql)
                result = await session.execute(stmt, params or {})

                columns = list(result.keys())
                raw_rows = result.fetchmany(eff_max_rows + 1)

                truncated = False
                if len(raw_rows) > eff_max_rows:
                    truncated = True
                    raw_rows = raw_rows[:eff_max_rows]
                elif len(raw_rows) == eff_max_rows and eff_max_rows < self.config.max_rows:
                    truncated = True

                # 3. Format row records preserving Decimal precision
                formatted_rows: list[dict[str, Any]] = []

                for row in raw_rows:
                    row_dict: dict[str, Any] = {}
                    for col_name, val in zip(columns, row, strict=False):
                        if isinstance(val, Decimal):
                            # Keep Decimal representation or stringified decimal
                            row_dict[col_name] = str(val)
                        elif hasattr(val, "isoformat"):
                            row_dict[col_name] = val.isoformat()
                        else:
                            row_dict[col_name] = val
                    formatted_rows.append(row_dict)

                # 4. Check serialized result byte budget
                serialized_size = len(json.dumps(formatted_rows, default=str).encode("utf-8"))
                if serialized_size > max_bytes:
                    logger.warning(
                        "Result size exceeded maximum byte budget",
                        bytes=serialized_size,
                        max_bytes=max_bytes,
                    )
                    raise SQLResultSizeExceededError(
                        f"Query result size ({serialized_size} bytes) exceeds "
                        f"limit ({max_bytes} bytes)."
                    )

                duration_ms = (time.perf_counter() - t0) * 1000

                return SQLQueryResult(
                    columns=columns,
                    rows=formatted_rows,
                    row_count=len(formatted_rows),
                    truncated=truncated,
                    duration_ms=duration_ms,
                )

        except TimeoutError as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            logger.warning(
                "SQL execution timed out",
                timeout_seconds=query_timeout_s,
                duration_ms=duration_ms,
            )
            raise SQLTimeoutError(
                f"SQL query execution exceeded timeout limit of {query_timeout_s}s."
            ) from exc
        except SQLResultSizeExceededError:
            raise
        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            err_msg = str(exc)
            # Check for PostgreSQL statement timeout message
            if "canceling statement due to statement timeout" in err_msg.lower():
                raise SQLTimeoutError(
                    f"PostgreSQL statement timeout ({statement_timeout_ms}ms) exceeded."
                ) from exc

            logger.error("SQL execution error", error=err_msg, duration_ms=duration_ms)
            raise SQLValidationError("Failed to execute database query safely.") from exc

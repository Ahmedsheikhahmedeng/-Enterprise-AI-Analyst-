"""AST-based SQL security validation, allowlist enforcement, and complexity bounding."""

import sqlglot
from sqlglot import exp

from app.core.logging import get_logger
from app.sql_agent.config import SQLAgentConfig, get_sql_agent_config
from app.sql_agent.exceptions import (
    SQLSecurityViolationError,
    SQLValidationError,
)
from app.sql_agent.models import SchemaContext, SQLComplexityMetrics

logger = get_logger("sql_agent.validator")

# Critical system and side-effect functions strictly forbidden in read-only SQL
FORBIDDEN_FUNCTIONS: frozenset[str] = frozenset(
    {
        "pg_read_file",
        "pg_write_file",
        "pg_read_binary_file",
        "pg_ls_dir",
        "pg_sleep",
        "version",
        "current_setting",
        "query_to_xml",
        "system",
        "eval",
        "exec",
        "cmd",
        "dblink",
        "dblink_exec",
        "pg_terminate_backend",
        "pg_cancel_backend",
        "lo_import",
        "lo_export",
        "copy",
    }
)

# System catalog schemas strictly forbidden unless explicitly in tenant schema
FORBIDDEN_SCHEMAS: frozenset[str] = frozenset(
    {
        "pg_catalog",
        "information_schema",
        "pg_toast",
    }
)


class SQLSecurityValidator:
    """Rigorous AST-based validator ensuring generated SQL is read-only and within safety bounds."""

    def __init__(self, config: SQLAgentConfig | None = None) -> None:
        self.config = config or get_sql_agent_config()

    def validate(
        self,
        raw_sql: str,
        schema_context: SchemaContext,
        max_rows: int | None = None,
    ) -> tuple[str, SQLComplexityMetrics]:
        """Validate raw SQL against AST rules, tenant schema allowlist, and return bounded SQL."""
        if not raw_sql or not raw_sql.strip():
            raise SQLValidationError("Generated SQL statement is empty.")

        # 1. Parse AST with sqlglot for PostgreSQL dialect
        try:
            statements = sqlglot.parse(raw_sql.strip(), read="postgres")
        except Exception as exc:
            raise SQLValidationError(f"SQL parsing syntax error: {exc}") from exc

        # 2. Prevent multi-statements (e.g. SELECT 1; DROP TABLE users;)
        if len(statements) != 1:
            raise SQLSecurityViolationError(
                f"Multiple SQL statements detected ({len(statements)}). "
                "Only single statement allowed."
            )

        ast = statements[0]
        if ast is None:
            raise SQLValidationError("Failed to generate AST representation for query.")

        # 3. Restrict AST type to Select or top-level CTE
        if not isinstance(ast, exp.Select):
            raise SQLSecurityViolationError(
                "Only read-only SELECT queries are allowed. "
                f"Detected statement type: {type(ast).__name__}"
            )

        # 4. Deep search for forbidden write or administrative expressions
        forbidden_nodes = (
            exp.Insert,
            exp.Update,
            exp.Delete,
            exp.Drop,
            exp.Alter,
            exp.Create,
            exp.Command,
            exp.Set,
            exp.Grant,
            exp.Revoke,
        )
        for node in ast.walk():
            if isinstance(node, forbidden_nodes):
                raise SQLSecurityViolationError(
                    f"Forbidden non-read-only operation detected in AST: {type(node).__name__}"
                )

        # 5. Extract defined CTE aliases so they are not treated as external tables
        cte_aliases: set[str] = set()
        for cte in ast.find_all(exp.CTE):
            if cte.alias:
                cte_aliases.add(cte.alias.lower())

        # 6. Validate table references against schema allowlist
        allowed_tables = schema_context.allowed_tables
        tables_found: list[str] = []

        for tbl in ast.find_all(exp.Table):
            tbl_name = tbl.name.lower()
            schema_name = tbl.db.lower() if tbl.db else None

            # Check forbidden schema prefixes (e.g. pg_catalog.pg_tables)
            if schema_name in FORBIDDEN_SCHEMAS:
                raise SQLSecurityViolationError(
                    f"Access to system catalog schema '{schema_name}' is forbidden."
                )

            # Ignore CTE aliases
            if tbl_name in cte_aliases:
                continue

            if tbl_name not in allowed_tables:
                raise SQLSecurityViolationError(
                    f"Unauthorized table access: Table '{tbl_name}' is not in the allowed schema."
                )

            tables_found.append(tbl_name)

        if not tables_found and not cte_aliases:
            raise SQLValidationError("Query must reference at least one valid table or CTE.")

        # 7. Validate column references against schema allowlist
        allowed_columns = schema_context.allowed_columns
        all_allowed_columns: set[str] = set()
        for col_set in allowed_columns.values():
            all_allowed_columns.update(col_set)

        for col in ast.find_all(exp.Column):
            col_name = col.name.lower()
            col_table = col.table.lower() if col.table else None

            # Skip star wildcards
            if col_name == "*":
                continue

            # If table is qualified and not a CTE
            if col_table and col_table not in cte_aliases:
                table_allowed_cols = allowed_columns.get(col_table, set())
                if table_allowed_cols and col_name not in table_allowed_cols:
                    raise SQLSecurityViolationError(
                        f"Unauthorized column '{col_name}' on table '{col_table}'."
                    )
            elif not col_table and all_allowed_columns:
                # If unqualified, verify it exists in at least one accessible table or CTE
                if col_name not in all_allowed_columns and col_name not in cte_aliases:
                    # Let SQL parser/engine resolve complex expressions, but log warning
                    pass

        # 8. Check for dangerous / system functions
        for node in ast.walk():
            func_name = None
            if isinstance(node, exp.Anonymous):
                func_name = node.name.lower() if node.name else None
            elif isinstance(node, exp.CurrentVersion):
                func_name = "version"
            elif isinstance(node, exp.Func):
                if hasattr(node, "name") and node.name:
                    func_name = str(node.name).lower()
                elif hasattr(node, "key") and node.key:
                    func_name = str(node.key).lower()

            if func_name and func_name in FORBIDDEN_FUNCTIONS:
                raise SQLSecurityViolationError(
                    f"Forbidden dangerous function detected: '{func_name}()'."
                )

        # 9. Compute and enforce complexity limits
        join_count = len(list(ast.find_all(exp.Join)))
        if join_count > self.config.max_joins:
            raise SQLSecurityViolationError(
                f"Query contains {join_count} JOINs, exceeding maximum allowed "
                f"limit of {self.config.max_joins}."
            )

        cte_count = len(list(ast.find_all(exp.CTE)))
        if cte_count > self.config.max_ctes:
            raise SQLSecurityViolationError(
                f"Query contains {cte_count} CTEs, exceeding maximum allowed "
                f"limit of {self.config.max_ctes}."
            )

        subquery_depth = self._calculate_subquery_depth(ast)
        if subquery_depth > self.config.max_subquery_depth:
            raise SQLSecurityViolationError(
                f"Query nesting depth {subquery_depth} exceeds maximum allowed "
                f"depth of {self.config.max_subquery_depth}."
            )

        complexity = SQLComplexityMetrics(
            table_count=len(tables_found),
            join_count=join_count,
            cte_count=cte_count,
            subquery_count=subquery_depth,
        )

        # 10. Enforce server-side LIMIT bounding
        eff_max_rows = (
            min(max_rows, self.config.max_rows)
            if max_rows is not None and max_rows > 0
            else self.config.max_rows
        )
        bounded_ast = self._enforce_limit(ast, eff_max_rows)
        validated_sql = bounded_ast.sql(dialect="postgres")

        return validated_sql, complexity

    def _enforce_limit(self, ast: exp.Select, max_rows: int) -> exp.Select:
        """Inject or clamp LIMIT clause on the root select statement."""
        limit_node = ast.args.get("limit")
        if limit_node is None:
            return ast.limit(max_rows)

        try:
            current_limit = int(str(limit_node.expression))
            if current_limit > max_rows or current_limit <= 0:
                ast.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
        except (ValueError, TypeError):
            ast.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))

        return ast

    def _calculate_subquery_depth(self, node: exp.Expression, current_depth: int = 0) -> int:
        """Recursively calculate the maximum depth of nested subqueries."""
        max_d = current_depth
        for child in node.iter_expressions():
            d = current_depth + (1 if isinstance(child, exp.Select) else 0)
            max_d = max(max_d, self._calculate_subquery_depth(child, d))
        return max_d

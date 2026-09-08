# Architecture — TASK 17: Secure SQL Agent & Structured Data Analysis

## 1. Executive Summary & Architecture Overview

The **Secure SQL Agent & Structured Data Analysis** layer enables the *Enterprise AI Analyst* platform to answer complex business and operational questions over structured relational datasets (PostgreSQL, connected data sources, uploaded CSV/XLSX tabular datasets) with enterprise-grade security guarantees.

Unlike conventional text-to-SQL setups that execute raw LLM text against databases, this architecture enforces a multi-tier defense-in-depth pipeline:

```text
User Question
      ↓
Structured Data Intent / Router
      ↓
Schema Discovery & Tenant Isolation Filter (SchemaDiscoveryService)
      ↓
SQL Planning & Constraint Formulation (SQLPlanner)
      ↓
SQL Generation (Deterministic Test Provider / OpenAI HTTP Provider)
      ↓
AST Parsing & Security Validation (SQLSecurityValidator using sqlglot)
   ├── Single Statement Enforcement (Rejection of multi-statement injections)
   ├── Read-Only AST Validation (SELECT / WITH only; zero DDL/DML allowed)
   ├── Schema Allowlist Bounding (Table & Column verification)
   ├── Dangerous Function Blocking (pg_read_file, pg_sleep, system, etc.)
   ├── Complexity Bounding (Max JOINs, Max CTEs, Max Subquery Depth)
   └── Server-Side LIMIT Enforcement (Automatic injection & clamping)
      ↓
Read-Only Database Execution (ReadOnlySQLExecutor)
   ├── Local Statement Timeout (`SET LOCAL statement_timeout = ...`)
   ├── Read-Only Transaction Guard (`SET LOCAL default_transaction_read_only = on`)
   ├── Row Limit & Result Byte Size Enforcement
   └── Decimal Precision Preservation
      ↓
Controlled Data Analysis (SQLResultAnalyzer via Pandas)
   ├── No eval() or exec()
   ├── Sum, Average, Min, Max, Count, Count Distinct
   └── Safe Percent Change Calculation (Division-by-zero & Null safe)
      ↓
Provenance Hashing (SQLProvenanceTracker: SHA-256 over normalized SQL)
      ↓
Persistence & Observability (AnalysisStep, AuditLog, LLMRequest, UsageEvent)
      ↓
Structured Response Output (`POST /api/v1/sql/query`)
```

---

## 2. Component Breakdown

### 2.1 Schema Discovery (`app/sql_agent/schema.py`)
- Discovers tables, columns, data types, primary keys, and relationships from `DataSource` and `Dataset` models.
- **Tenant Scoping**: Rejects cross-tenant access attempts immediately with `SQLTenantMismatchError`.
- **In-Memory Schema Caching**: Caches discovered schemas with a configurable TTL (`SQL_SCHEMA_CACHE_TTL_SECONDS = 300`) and provides an explicit `invalidate(org_id, datasource_id)` method.

### 2.2 SQL Planning (`app/sql_agent/planner.py`)
- Analyzes natural language questions against the schema context.
- Identifies relevant tables and analytical intents (`SUM`, `AVG`, `COUNT`, `MIN`, `MAX`).
- Extracts temporal filters (e.g., years `2025`, quarters `Q1`-`Q4`).

### 2.3 AST Security Validation (`app/sql_agent/validator.py`)
The validator uses `sqlglot` to parse the PostgreSQL AST:
1. **Multi-Statement Prevention**: Rejects any input where `len(statements) != 1`.
2. **Statement Type Enforcement**: Requires root expression to be `exp.Select`.
3. **Disallowed Operations**: Completely forbids `exp.Insert`, `exp.Update`, `exp.Delete`, `exp.Drop`, `exp.Alter`, `exp.Create`, `exp.Command`, `exp.Set`, `exp.Grant`, `exp.Revoke`.
4. **Table Allowlist**: Ensures every queried table exists in `SchemaContext.allowed_tables` (while properly recognizing CTE aliases).
5. **Column Allowlist**: Validates column references against `SchemaContext.allowed_columns`.
6. **Dangerous Function Blocking**: Prohibits dangerous system functions (`pg_read_file`, `pg_write_file`, `pg_sleep`, `version`, `query_to_xml`, `system`, etc.).
7. **System Catalog Blocking**: Prohibits access to `pg_catalog`, `information_schema`, etc.
8. **Complexity Limits**:
   - Max JOINs: 5 (`SQL_MAX_JOINS`)
   - Max CTEs: 3 (`SQL_MAX_CTES`)
   - Max Subquery Depth: 2 (`SQL_MAX_SUBQUERY_DEPTH`)
9. **LIMIT Enforcement**: Automatically injects or clamps the `LIMIT` clause to `<= SQL_MAX_ROWS`.

### 2.4 Read-Only Execution Engine (`app/sql_agent/executor.py`)
- Executes queries within an isolated transaction configured with:
  - `SET LOCAL statement_timeout = {SQL_STATEMENT_TIMEOUT_MS}`
  - `SET LOCAL default_transaction_read_only = on`
- Wrapped in an `asyncio.timeout` block (`SQL_QUERY_TIMEOUT_SECONDS = 10.0`).
- Enforces row count bounding and maximum result byte size (`SQL_MAX_RESULT_BYTES = 5,000,000`).
- Preserves exact `Decimal` representation for monetary and numerical columns.

### 2.5 Controlled Analytical Layer (`app/sql_agent/analyzer.py`)
- Uses Python and Pandas without any arbitrary code execution (`eval()` and `exec()` are forbidden).
- Automatically calculates sums, averages, minimums, maximums, and overall trends.
- Computes percentage changes with zero-division handling (`(new - old) / old * 100` returns `None` if `old == 0`).

### 2.6 Provenance Tracking (`app/sql_agent/provenance.py`)
- Normalizes query whitespace and standardizes terminators.
- Calculates an SHA-256 cryptographic hash (`sql_hash`).
- Constructs an immutable provenance record linking `sql_hash`, `datasource_id`, `tables_used`, `columns_used`, `row_count`, and `duration_ms`.

---

## 3. Security Architecture & Threat Model

| Threat Vector | Defense Mechanism |
|---|---|
| **SQL Injection (Multi-Statement)** | AST parsing with `sqlglot` rejects `len(statements) != 1`. |
| **SQL Data Modification / Deletion** | AST root must be `exp.Select`; write nodes raise `SQLSecurityViolationError`; DB transaction set to `READ ONLY`. |
| **Data Exfiltration / Unauthorized Tables** | Strict allowlist check against `SchemaContext.allowed_tables`. |
| **Privilege Escalation via System Catalogs** | Forbidden schemas (`pg_catalog`, `information_schema`) blocked by AST validator. |
| **Command Execution / File System Access** | Forbidden function list (`pg_read_file`, `system`, `cmd`) blocked by AST validator. |
| **Denial of Service (Runaway Queries)** | Database statement timeout (`statement_timeout = 5000ms`), application timeout (10s), row limit (5000), result byte size limit (5MB). |
| **Cross-Tenant Data Access** | `SchemaDiscoveryService` validates `datasource.organization_id == tenant.organization_id` before generating schema context. |
| **Prompt Injection via Question Text** | User prompt cannot override system rules; generated SQL must survive AST security validation. |

---

## 4. Operational Telemetry & Persistence

Each SQL Agent query execution automatically logs to the central telemetry tables:
1. **`AuditLog`**: Records event `sql_agent.query_execute` with `resource_type="data_source"`, `resource_id`, and metadata containing `sql_hash`, `tables_used`, and `duration_ms`.
2. **`LLMRequest`**: Records model, tokens consumed, latency, and estimated cost in USD.
3. **`UsageEvent`**: Records consumption events for tenant billing.
4. **`AnalysisStep`**: When linked to an `AnalysisRun`, records distinct steps for `sql_planning` and `sql_execution`.

---

## 5. Known Limitations

1. **Dialect Support**: The primary dialect currently supported and validated is PostgreSQL. Other dialects (BigQuery, Snowflake) will be integrated via provider extensions.
2. **Interactive Charting**: Results are returned in structured tabular JSON; frontend visualization rendering is delegated to UI components.
3. **Cross-DataSource Federation**: Queries cannot join across different connected databases in a single SQL statement; federation is handled at the application layer.

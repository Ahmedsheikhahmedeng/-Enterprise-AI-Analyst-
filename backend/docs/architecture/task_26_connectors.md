# TASK 26 — Enterprise Data Connectors & Unified Data Access Layer

## 1. Overview

The Unified Data Access Layer provides a standardized, decoupled connector abstraction for external data sources within the Enterprise AI Analyst platform. It eliminates direct source-specific coupling from AI agents, the SQL Agent, RAG pipelines, and background job workers by routing all interactions through a capability-driven connector protocol, strict tenant boundary enforcement, AST-level query validation, and comprehensive secret redaction.

```
                    ┌──────────────────────────────────────────────┐
                    │      Agent Runtime / AI Analyst / Jobs       │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │         Typed Tools / App Services           │
                    │   (datasource.list, schema, preview, query)  │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │          TenantContext & RBAC Check          │
                    │     (Tenant isolation + granular perms)      │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │     Query / Schema / Sync / Conn Services    │
                    └──────┬───────────────┬───────────────┬───────┘
                           │               │               │
                           ▼               ▼               ▼
                   ┌──────────────┐ ┌─────────────┐ ┌─────────────┐
                   │ Secure AST   │ │ Redis Cache │ │ Audit &     │
                   │ Validator    │ │ (Isolated)  │ │ Metrics     │
                   └──────┬───────┘ └─────────────┘ └─────────────┘
                          │
                          ▼
             ┌─────────────────────────┐
             │   Connector Registry    │
             └────────────┬────────────┘
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  PostgreSQL  │   │     CSV      │   │    Excel     │
│  Connector   │   │  Connector   │   │  Connector   │
└──────────────┘   └──────────────┘   └──────────────┘
```

---

## 2. Connector Architecture & Capabilities

Connectors adhere to the `DataConnector` protocol:

- `test_connection(configuration) -> ConnectionTestResult`
- `get_schema(datasource_id, organization_id, configuration) -> SchemaModel`
- `execute_query(request, configuration) -> QueryResult`
- `preview_data(datasource_id, organization_id, configuration, target_name, max_rows) -> PreviewResult`
- `health_check(configuration) -> ConnectorHealthResult`

### Capability Enforcement

Each connector declares its supported capabilities via `ConnectorCapabilities`:
- `schema_read`: Ability to introspect tables, columns, primary keys, foreign keys.
- `query`: Ability to execute read-only queries with parameterized inputs.
- `write`: Disabled across analytical connectors.
- `sync`: Ability to perform scheduled or ad-hoc data synchronization.
- `streaming`: Streaming ingestion capability.
- `files`: File-based connector flag (CSV, Excel).

If a caller invokes an unsupported operation (e.g. `execute_query` on a connector without `query=True`), the system raises `UnsupportedCapabilityError`.

---

## 3. Concrete Connector Implementations

### 3.1 PostgreSQL Connector
- **Connection Test:** Validates connection within a strict timeout boundary without leaking credentials.
- **Schema Discovery:** Introspects `information_schema.tables`, `columns`, and constraint keys for primary and foreign keys.
- **Safe Query Execution:** Read-only transaction enforcement (`SET TRANSACTION READ ONLY`), timeout limits (`statement_timeout`), and bounded row extraction.
- **Security:** AST query validation via `SQLSecurityValidator` preventing DDL/DML, dangerous system schema queries, and unauthorized function calls.

### 3.2 CSV Connector
- **File Validation:** Verifies existence, path containment, and maximum file size limits (50 MB default).
- **Streaming Schema Inference:** Reads CSV headers and sample rows to infer column types (`integer`, `float`, `datetime`, `boolean`, `string`).
- **Formula Injection Defense:** Sanitizes all string values starting with formula trigger characters (`=`, `+`, `-`, `@`, `\t`, `\r`) by prepending a single quote (`'`).
- **Preview & Query Preparation:** Provides bounded row previews up to 1,000 rows max.

### 3.3 Excel Connector
- **Workbook Introspection:** Uses `openpyxl` with `read_only=True` to stream sheet names and cell values without loading entire workbooks into memory.
- **Multi-Sheet Support:** Represents each worksheet as an independent table within the unified schema model.
- **Cell Sanitization:** Defends against formula injection attacks across all sheet cells.
- **Resource Constraints:** Enforces sheet limits, row limits, and column limits.

---

## 4. Secret Management & Redaction

- **Symmetric Encryption:** Sensitive credentials (passwords, tokens, API keys) in `DataSource.configuration` are encrypted at rest using `SecretProvider` (Fernet symmetric key derived from system secret keys).
- **Zero Credential Leakage:** `SecretProvider.redact_config()` replaces all sensitive keys (`password`, `secret`, `token`, `key`, `credential`, etc.) with `"***REDACTED***"` before logging, auditing, trace propagation, or returning API responses.

---

## 5. Redis Schema Caching

To prevent redundant schema discovery overhead, schemas are cached in Redis:
- **Key Scheme:** `schema:{organization_id}:{datasource_id}:{version}`
- **TTL:** 3600 seconds (1 hour default).
- **Tenant Isolation:** Tenant ID is strictly embedded in the cache key prefix, preventing cross-tenant key collisions or cache poisoning.
- **Explicit Invalidation:** Triggered on schema updates, sync completion, or forced refreshes.

---

## 6. Provenance & Observability

Every query execution produces a `QueryResult` containing a rich `provenance` dictionary:
- `organization_id`
- `datasource_id`
- `connector_type`
- `query_hash` (SHA-256 hash of normalized query text; zero secrets included)
- `executed_at` (UTC timestamp)
- `row_count`
- `execution_time_ms`

Metrics are recorded via `ConnectorInstrumentation` using Prometheus-compatible low-cardinality counters and histograms:
- `connector_connection_success_total` / `failure_total`
- `connector_query_success_total` / `failure_total`
- `connector_query_duration_seconds`
- `connector_schema_discovery_duration_seconds`
- `connector_sync_records_total`

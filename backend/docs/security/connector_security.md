# Security Controls: Enterprise Data Connectors & Access Layer

## 1. Threat Model & Security Principles

The Unified Data Access Layer acts as the critical trust boundary between the Enterprise AI Analyst platform and external database/file storage systems. It enforces defense-in-depth principles:

1. **Strict Multi-Tenant Isolation:** No tenant can access, introspect, execute queries on, or invalidate cache for another tenant's data sources.
2. **Zero Plaintext Secrets:** Passwords, API tokens, and database credentials are encrypted at rest and redacted from logs, traces, API responses, and audit logs.
3. **No Raw SQL Agent Bypass:** AI agents cannot bypass `SQLSecurityValidator` or execute arbitrary non-SELECT statements.
4. **Untrusted File Input Hardening:** All CSV and Excel files are validated against path traversal, formula injection, zip bombs, and memory exhaustion.
5. **Least-Privilege RBAC:** Granular permissions govern data source lifecycle, schema introspection, testing, querying, and synchronization.

---

## 2. Granular RBAC Permissions

The following system permissions are registered in `app/rbac/catalog.py`:

| Permission | Description | Admin | Analyst | Viewer |
|---|---|:---:|:---:|:---:|
| `datasource.read` | View data source metadata, preview, and status | Yes | Yes | Yes |
| `datasource.create` | Register new data sources | Yes | No | No |
| `datasource.update` | Modify data source configuration or status | Yes | No | No |
| `datasource.delete` | Unregister / delete data sources | Yes | No | No |
| `datasource.test` | Trigger connection testing | Yes | Yes | No |
| `datasource.schema` | Introspect and refresh table/column schemas | Yes | Yes | No |
| `datasource.query` | Execute read-only queries | Yes | Yes | No |
| `datasource.sync` | Trigger full synchronization jobs | Yes | Yes | No |

---

## 3. SQL Security Validation Boundary

All queries targeted at relational connectors (PostgreSQL) must pass `SQLSecurityValidator`:
- **Statement Whitelist:** Only `SELECT` and `WITH` (Common Table Expressions) statements are permitted.
- **DDL / DML Blocking:** Any attempt to execute `DROP`, `ALTER`, `CREATE`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, or `GRANT` is rejected with `SQLSecurityViolationError`.
- **Dangerous Functions:** Blocking functions like `pg_sleep`, `pg_read_file`, `system`, `xp_cmdshell`, etc.
- **System Schema Blocking:** Blocking queries targeting `pg_catalog`, `information_schema` directly from ad-hoc user query paths.
- **Transaction Safety:** Read-only mode is enforced via connection parameters and statement timeouts.

---

## 4. Formula Injection Neutralization

When processing CSV or Excel files, cell contents starting with formula triggers can compromise spreadsheet software upon export (CSV Injection / Formula Injection).

The connectors enforce cell sanitization:
- **Triggers:** `=`, `+`, `-`, `@`, `\t`, `\r`
- **Sanitization Rule:** Cells matching triggers are prefixed with a single quote (`'`), ensuring spreadsheet applications treat the content as literal text rather than executable formulas.

---

## 5. Secret Encryption & Redaction

- **Symmetric Encryption:** Database configurations are encrypted using `SecretProvider` with AES-256 / Fernet key derivation.
- **Redaction Pipeline:**
  ```python
  REDACTED_FIELDS = {
      "password",
      "secret",
      "token",
      "api_key",
      "access_key",
      "secret_key",
      "credentials",
      "private_key",
      "auth",
  }
  ```
- **Audit & Log Safety:** When auditing `DATASOURCE_CREATED`, `DATASOURCE_UPDATED`, or `CONNECTION_TESTED`, all configuration payloads pass through `SecretProvider.redact_config()`.

---

## 6. Tenant Isolation Verification

Multi-tenancy is verified via automated security tests:
- **Direct Access Prevention:** Requesting `GET /api/v1/data-sources/{id}` for an ID belonging to Organization B while in TenantContext A returns `404 Not Found`.
- **Query & Schema Prevention:** Invoking schema discovery or query execution across tenant boundaries raises `DataSourceNotFoundError`.
- **Cache Key Namespace:** Redis keys follow `schema:{organization_id}:{datasource_id}:{version}`, preventing key collisions or cache contamination.

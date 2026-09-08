# Architecture Specification: TASK 19 — Enterprise Report Generation & Export

## 1. System Overview

The **Enterprise Report Generation & Export** layer transforms analytical results synthesized by `AIAnalystService` (`AnalysisRun`, `UnifiedEvidence`, `DataConflict`) into structured, verifiable, versioned, and exportable executive intelligence documents.

```text
AIAnalystService (TASK 18)
      ↓ (AnalysisRun, AnalysisStep)
ReportService (TASK 19)
      ↓
ReportBuilder (Structured extraction, deterministic content hash)
      ↓
ReportValidator (Anti-hallucination, phantom citation rejection, numeric validation)
      ↓
ReportVersionManager (Transaction-safe versioning, immutable published snapshots)
      ↓
PostgreSQL Storage (reports, report_versions)
      ↓
Renderers & Exporters
 ┌────┼──────────────┐
 ↓    ↓              ↓
Markdown HTML       PDF (ReportLab A4)
                     ↓
                    CSV (ReportTable tabular rows)
```

---

## 2. Core Modules & Directory Structure

```text
app/reports/
├── __init__.py          # Public exports
├── config.py            # ReportConfig settings dataclass
├── exceptions.py        # Typed exception hierarchy derived from AppException
├── models.py            # Domain models (ReportDocument, KeyFinding, ReportMetric, ReportTable, etc.)
├── schemas.py           # Pydantic request/response schemas for REST API
├── policies.py          # ReportSecurityPolicy (tenant validation & path traversal prevention)
├── builder.py           # ReportBuilder (extraction from analysis payload, content hashing)
├── validator.py         # ReportValidator (evidence citation & structural validation)
├── versioning.py        # ReportVersionManager (concurrency-safe version increment & publish)
├── service.py           # ReportService orchestration with audit logging
├── renderers/
│   ├── __init__.py
│   ├── base.py          # BaseReportRenderer abstract protocol
│   ├── markdown.py      # MarkdownRenderer (deterministic GitHub-Flavored Markdown)
│   ├── html.py          # HTMLRenderer (semantic, inline CSS, RTL/LTR support, XSS-escaped)
│   └── pdf.py           # PDFRenderer (ReportLab A4 layout, headers/footers, table styling)
└── exporters/
    ├── __init__.py
    └── csv.py           # CSVExporter (strictly exports verified ReportTable rows)
```

---

## 3. Domain Model (`ReportDocument`)

The `ReportDocument` encapsulates a structured representation of enterprise intelligence:

- **Metadata**: `report_id`, `organization_id`, `analysis_run_id`, `title`, `subtitle`, `status` (`draft`, `generated`, `published`, `archived`, `failed`), `version`, `created_by`, `created_at`, `updated_at`, `published_at`.
- **Core Sections**:
  - `executive_summary`: Concise summary directly grounded in cited evidence.
  - `key_findings`: List of `KeyFinding` objects (`id`, `title`, `statement`, `importance`, `citations`, `numeric_values`).
  - `metrics`: Structured `ReportMetric` objects (`name`, `value`, `unit`, `period`, `source`).
  - `tables`: List of `ReportTable` objects (`id`, `title`, `columns`, `rows`, `source_refs`).
  - `charts`: Declarative `ChartSpec` objects (`id`, `type`, `title`, `x_axis`, `y_axis`, `series`, `source_refs`).
  - `evidence`: Normalized `ReportEvidence` items (`id`, `type`, `title`, `is_calculated`, `metadata`).
  - `conflicts`: List of `ReportConflict` objects (`field`, `source_a`, `value_a`, `source_b`, `value_b`, `severity`, `description`).
  - `methodology`: Concise methodological disclosure without exposing proprietary chain-of-thought or raw system prompts.
  - `data_sources`: Sanitized datasource identifiers and table/document names without leaking credentials or secrets.
  - `diagnostics`: Latency, branch counts, and cost telemetry.
- **Audit & Version Metadata**: `prompt_version`, `generator_version`, `template_version`, `content_hash` (SHA-256), `language`, `direction` (`ltr` or `rtl`).

---

## 4. PostgreSQL Integration & Versioning

### Database Schema Extension
- Extended existing `reports` table:
  - `current_version`: Integer (default 1).
  - `published_at`: Timestamp with time zone (nullable).
  - `content_hash`: String(64) representing the SHA-256 canonical hash of the current version.
- Created `report_versions` table:
  - `id`: UUID primary key.
  - `report_id`: Foreign key to `reports.id` (CASCADE on delete).
  - `organization_id`: Tenant identifier with index `ix_report_versions_org_id`.
  - `version_number`: Integer version number.
  - `title`: Version-specific title.
  - `status`: Version status (`draft`, `published`, `archived`).
  - `content`: Rendered Markdown representation.
  - `document_data`: Full canonical JSON representation of `ReportDocument`.
  - `content_hash`: Deterministic SHA-256 hash.
  - `created_by`: User UUID.
  - `created_at`: Creation timestamp.
  - Unique constraint: `uq_report_version_number` on `(report_id, version_number)`.

### Immutability & Concurrency
- **Drafts**: Editable and can be revised in-place before publishing.
- **Published Versions**: Permanently immutable. Any modification to a published report creates an incremented version (e.g., v1 -> v2) while preserving the published historical record.
- **Publish Operation**: Marks the current version as `published`, records `published_at`, and updates the root `reports.status`.

---

## 5. Evidence Grounding & Anti-Hallucination

- **No Evidence → No Claim**: Every finding, claim, and metric must reference valid evidence identifiers (`[S1]`, `[R1]`).
- **Phantom Citation Rejection**: `ReportValidator` verifies that all cited markers exist in the verified `evidence` registry; unknown markers trigger `ReportValidationError`.
- **Conflict Preservation**: Factual and numerical discrepancies between SQL calculations and document assertions (e.g., $120M vs $100M) are explicitly preserved in the `conflicts` section and rendered in warning callouts.
- **Zero Re-Analysis**: Reports are constructed from the stored output of `AnalysisRun` and `AnalysisStep` without re-running expensive or non-deterministic SQL/RAG queries.

---

## 6. Rendering & Export Formats

1. **Markdown (`MarkdownRenderer`)**:
   - Clean, deterministic GitHub-Flavored Markdown.
   - Includes Executive Summary, Key Findings, Metrics tables, Conflicts, Methodology, and Sources with citations.

2. **HTML (`HTMLRenderer`)**:
   - Standalone semantic HTML5 document.
   - Self-contained modern CSS styling without external scripts or fonts.
   - Strict HTML entity escaping for untrusted textual content.
   - Bidirectional text layout support: `dir="rtl"` for Arabic (`ar`), `dir="ltr"` for English and Turkish.

3. **PDF (`PDFRenderer`)**:
   - Generated using `reportlab` with standard A4 page layout.
   - Custom `NumberedCanvas` providing running headers, dates, and dynamic "Page X of Y" pagination.
   - Semantic color palette, table borders, metric cards, and conflict alert boxes.
   - Secure: no remote web requests, no executable JavaScript, no external font downloads.

4. **CSV (`CSVExporter`)**:
   - Strictly exports tabular rows from `ReportDocument.tables` (with metric fallback).
   - Prevents arbitrary database querying; only verified report table data is serialized.

---

## 7. Security & Multi-Tenancy

- **Tenant Isolation**: Every report and report version carries `organization_id`. All repository queries and REST endpoints enforce tenant boundaries via `TenantContext`. Cross-tenant access attempts immediately raise `ReportAuthorizationError` (403/404).
- **AnalysisRun Verification**: When generating a report from `analysis_run_id`, `ReportService` verifies that `AnalysisRun.organization_id == TenantContext.organization_id`.
- **Filename Sanitization**: Export filenames are sanitized against directory traversal attacks (e.g., `../../secret.pdf` is stripped to safe alphanumeric tokens).
- **Credential Redaction**: Connection strings, passwords, and host credentials in data source metadata are redacted before insertion into report documents.

---

## 8. Role-Based Access Control (RBAC)

The permission catalog includes granular permissions for report operations:
- `reports.read`: View reports, versions, and metadata.
- `reports.create`: Generate reports from analysis runs.
- `reports.update`: Edit draft report versions.
- `reports.publish`: Publish a report version to immutable status.
- `reports.export`: Export reports to Markdown, HTML, PDF, or CSV.
- `reports.archive`: Mark active reports as archived.

### Role Mappings
- **Admin**: All report permissions (`read`, `create`, `update`, `publish`, `export`, `archive`).
- **Analyst**: Full operational permissions (`read`, `create`, `update`, `publish`, `export`, `archive`).
- **Viewer**: Read-only visibility (`reports.read`).

---

## 9. REST API Specification

Mounted at `/api/v1/reports`:

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `POST` | `/api/v1/reports/from-analysis` | `reports.create` | Synthesize a new report from an existing `AnalysisRun` |
| `GET` | `/api/v1/reports` | `reports.read` | List paginated reports for tenant with optional status filter |
| `GET` | `/api/v1/reports/{report_id}` | `reports.read` | Retrieve report metadata and current version document |
| `GET` | `/api/v1/reports/{report_id}/versions/{version}` | `reports.read` | Retrieve a specific historical version |
| `POST` | `/api/v1/reports/{report_id}/publish` | `reports.publish` | Publish current or specified version to immutable status |
| `POST` | `/api/v1/reports/{report_id}/archive` | `reports.archive` | Archive an active report |
| `GET` | `/api/v1/reports/{report_id}/export/markdown` | `reports.export` | Export report content as Markdown (`.md`) |
| `GET` | `/api/v1/reports/{report_id}/export/html` | `reports.export` | Export report content as standalone HTML (`.html`) |
| `GET` | `/api/v1/reports/{report_id}/export/pdf` | `reports.export` | Export report content as paginated A4 PDF (`.pdf`) |
| `GET` | `/api/v1/reports/{report_id}/export/csv` | `reports.export` | Export tabular report data as CSV (`.csv`) |

---

## 10. Audit Logging

Sensitive report actions record structured entries in the `audit_logs` table:
- `report.created`: New report draft created from analysis run.
- `report.viewed`: Report or specific version accessed.
- `report.version_created`: Subsequent version generated for report.
- `report.published`: Report version transitioned to immutable published state.
- `report.archived`: Report status updated to archived.
- `report.exported`: Report exported in MD, HTML, PDF, or CSV format.

---

## 11. Known Limitations

1. **Client-Side Visual Charts**: `ChartSpec` defines declarative chart configurations (bar, line, pie). In this phase, PDF reports render chart summaries and structured tables rather than rasterizing client-side canvas charts.
2. **Deterministic Offline Generation**: Reports are generated deterministically from analysis run outputs without invoking external LLMs for formatting, ensuring deterministic performance and zero token costs during export.
3. **Single Active Template**: The system includes the `executive` template layout; additional specialized layouts (`detailed`, `technical`) can be added without altering the core builder contracts.

---

## 12. Verification & Testing

- **Unit Tests (`tests/unit/test_reports.py`)**: 14 tests covering report builder, validator (phantom citation detection), Markdown, HTML, PDF, and CSV renderers, and security policies.
- **Integration Tests (`tests/integration/test_reports.py`)**: 6 tests verifying end-to-end flow from `AIAnalystService.ask` to report creation, conflict preservation, multi-tenant isolation, version immutability, REST API lifecycle, and RBAC enforcement.
- **PDF Inspection**: Validated via `pypdf.PdfReader` ensuring PDF header `%PDF-`, valid page count, and title extraction.

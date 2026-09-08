# Security Controls: Dataset Ingestion & Materialization

## 1. Multi-Tenant Isolation Boundaries

The Dataset Materialization Pipeline strictly enforces multi-tenancy at every tier:
1. **Tenant-Scoped Datasets:** Every database query filters by `organization_id` derived exclusively from `TenantContext`. User-supplied IDs cannot modify or bypass tenant boundaries.
2. **Cross-Tenant DataSource Isolation:** A dataset belonging to Organization A cannot ingest data from a DataSource belonging to Organization B.
3. **Partitioned Storage:** Materialized datasets are written into isolated directory paths:
   ```text
   storage/datasets/{organization_id}/{dataset_id}/v{version}/data.jsonl
   ```
4. **Analytical Discovery Guard:** Non-ready datasets are filtered out from Text-to-SQL schema discovery, preventing agents from issuing queries on incomplete or failing datasets.

---

## 2. Granular RBAC Permissions

The following permissions govern dataset operations:

| Permission | Description | Admin | Analyst | Viewer |
|---|---|:---:|:---:|:---:|
| `dataset.read` | View dataset metadata, schemas, and quality scorecards | Yes | Yes | Yes |
| `dataset.create` | Register new datasets | Yes | No | No |
| `dataset.update` | Modify dataset metadata and classification | Yes | No | No |
| `dataset.delete` | Delete or archive datasets | Yes | No | No |
| `dataset.ingest` | Trigger materialization and ingestion pipeline | Yes | Yes | No |
| `dataset.profile` | Inspect detailed statistical column profiles | Yes | Yes | No |
| `dataset.versions` | Inspect historical materialization snapshots | Yes | Yes | No |

---

## 3. Credential Redaction & Provenance Safety

- All database connection credentials from source `DataSource` entities are decrypted strictly in-memory during ingestion and masked with `"***REDACTED***"` before logging or writing audit trails.
- Lineage records store SHA-256 cryptographic hashes (`source_fingerprint`, `schema_fingerprint`, `content_fingerprint`) rather than raw connection parameters or plaintext payloads.

---

## 4. PII Classification & Data Hardening

The pipeline scans non-null values for:
- Email addresses
- Phone numbers
- Credit card numbers
- National ID / SSN patterns

Detected categories are assigned as `pii_classification` on `DatasetColumn` and elevate dataset sensitivity to `SENSITIVE` or `INTERNAL`, providing metadata guidance for downstream masking policies.

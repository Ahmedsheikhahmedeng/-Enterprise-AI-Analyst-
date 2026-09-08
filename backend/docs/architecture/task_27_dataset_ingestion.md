# TASK 27 — Enterprise Data Ingestion & Dataset Materialization Pipeline

## 1. Executive Summary

The Enterprise Data Ingestion & Dataset Materialization Pipeline provides an automated, decoupled, and verifiable pathway for converting raw data from connectors (PostgreSQL, CSV, Excel) into standardized, profiled, validated, deduplicated, and versioned `Dataset` entities.

```
DataSource / Connector (Task 26)
        │
        ▼
ConnectorDatasetReader (Chunked / Bounded Streaming)
        │
        ▼
Validation & Schema Normalization (Arabic, Turkish, Unicode, Reserved Words)
        │
        ▼
Statistical Profiling & Data Quality Scoring (Bounded Memory)
        │
        ▼
Deduplication Engine (Exact Hash, Primary Key, Composite Key)
        │
        ▼
Dataset Materialization & Zero-Downtime Version Promotion (v1 READY -> v2 INGESTING -> v2 READY / v1 STALE)
        │
        ▼
Dataset & DatasetColumn Entities (Metadata, PII Classification, Lineage)
        │
        ├──────────────────────────┬──────────────────────────┐
        ▼                          ▼                          ▼
   SQL Analyst Agent          RAG Adapter            Agent Runtime Tools
(Schema Context / Queries)  (Document Cards)         (dataset.* Typed Tools)
```

---

## 2. Ingestion Stages & Lifecycle

The pipeline operates across explicit deterministic execution stages:
1. **VALIDATING:** Source connection test, bounds checking, max row bounds (up to 5,000,000 rows), and tenant scoping.
2. **PROFILING:** Streaming computation of null ratios, distinct sample estimates, numeric min/max/mean/median, text length distributions, and date ranges.
3. **NORMALIZING:** Normalizes column headers across languages (including Arabic `اسم العميل` -> `اسم_العميل` and Turkish `müşteri_adı`), disambiguates duplicates case-insensitively, and protects SQL keywords.
4. **DEDUPLICATING:** Removes exact duplicate rows or key collisions according to the configured `DeduplicationStrategy`.
5. **MATERIALIZING:** Writes processed records to partitioned JSONL durable storage (`LocalDatasetWriter`).
6. **PROMOTING:** Computes cryptographic SHA-256 fingerprints (`source_fingerprint`, `schema_fingerprint`, `content_fingerprint`) and atomically promotes the new `DatasetVersion`.

### Zero-Downtime Version Transition
- `v1` is `READY`.
- A new ingestion run begins for `v2`: `v2` is created with status `INGESTING`. `v1` remains fully accessible and `READY` for analytical workloads.
- When `v2` successfully completes materialization, `v2` becomes `READY` and `v1` transitions to `STALE`.
- If `v2` fails at any point, `v2` is marked `FAILED`, while `v1` remains `READY`.

---

## 3. Data Quality & PII Sensitivity Scoring

### Data Quality Score ($0.0 \to 1.0$)
$$Quality = 1.0 - (0.4 \times NullRatio + 0.3 \times DuplicateRatio + 0.3 \times InvalidRatio)$$
Datasets with low null counts, zero duplicates, and clean typing achieve scores $\ge 0.90$.

### PII Classification
The deterministic `PIIDetector` evaluates column names and sample values for high-confidence markers:
- `EMAIL`
- `PHONE`
- `CREDIT_CARD`
- `NATIONAL_ID`

If any high-risk identifier (credit card, national ID) is detected, the dataset classification is promoted to `SENSITIVE`. If contact info is detected, it is marked `INTERNAL`. Otherwise, it defaults to `PUBLIC`.

---

## 4. Downstream Integrations

1. **SQL Analyst Agent:** Discovers dataset schemas via `SchemaDiscoveryService.get_schema_context()`. Non-ready datasets (`created`, `ingesting`, `failed`, `stale`) are strictly hidden to prevent analytical failures.
2. **RAG Adapter (`DatasetRAGAdapter`):** Formats tabular records into readable markdown key-value cards when `ingestion_mode` is `RAG_ENABLED` or `BOTH`.
3. **Agent Runtime:** Typed tools (`dataset.list`, `dataset.get`, `dataset.profile`, `dataset.versions`, `dataset.quality`) exposed under `ANALYST_AGENT` and `RESEARCH_AGENT` profiles.
4. **Background Jobs:** Long-running materialization runs asynchronously via `DatasetIngestionTask` (`JobType.DATASET_INGESTION`) with incremental progress reporting.

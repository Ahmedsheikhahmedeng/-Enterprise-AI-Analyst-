# Architecture Specification: TASK 18 — Unified AI Analyst Orchestrator

## 1. System Overview

The **Unified AI Analyst Orchestrator** is the central orchestration layer uniting structured database querying (`SQLAgentService`) and unstructured document retrieval (`RAGService`) into a cohesive **Enterprise AI Analyst**.

```text
User Question
      ↓
Query Intent & Route Classification (AnalystQueryRouter)
      ↓
Execution Plan Assembly (DeterministicAnalystPlanner)
      ↓
Parallel Branch Execution (ParallelAnalystExecutor via asyncio.gather)
      ├── SQL Branch (ReadOnlySQLExecutor)
      └── RAG Branch (RAGService)
      ↓
Evidence Consolidation & Namespacing (EvidenceMerger -> S1, S2... / R1, R2...)
      ↓
Contradiction & Discrepancy Detection (ConflictDetector)
      ↓
Grounded Answer Synthesis & Citation Repair (GroundingValidator)
      ↓
Telemetry & Audit Persistence (AnalysisRun, AnalysisStep, AuditLog, UsageEvent)
      ↓
Unified Analyst Response (AnalystResult)
```

---

## 2. Core Modules & Responsibilities

### `AnalystQueryRouter` (`app/analyst/router.py`)
- Analyzes natural language questions in English, Arabic, and Turkish.
- Detects structured intents (`revenue`, `growth`, `total`, `quarter`, `مبيعات`, `أرباح`, `gelir`, `satış`).
- Detects unstructured document intents (`report`, `policy`, `why`, `explanation`, `تقرير`, `لماذا`, `rapor`, `neden`).
- Classifies questions into:
  - `SQL`: Structured calculations over relational datasets when a target datasource is provided.
  - `RAG`: Qualitative questions concerning text documents and policies.
  - `HYBRID`: Multi-part or explanatory questions requiring quantitative SQL derivation alongside document explanations.
  - `NONE`: Fallback route safely defaulting to document retrieval.

### `DeterministicAnalystPlanner` (`app/analyst/planner.py`)
- Builds an explicit, immutable `ExecutionPlan`.
- Instantiates concrete `ExecutionBranch` specifications with individual timeouts and query representations.
- Deduplicates identical branches and enforces branch budget limits (`ANALYST_MAX_BRANCHES`).

### `ParallelAnalystExecutor` (`app/analyst/executor.py`)
- Concurrently executes plan branches using bounded concurrency via `asyncio.gather`.
- Enforces an absolute shared request deadline (`ANALYST_TOTAL_TIMEOUT_SECONDS`) using `asyncio.timeout`.
- Handles partial branch failures gracefully:
  - SQL succeeds + RAG fails -> returns partial structured answer, flags `degraded=True, is_partial=True`.
  - RAG succeeds + SQL fails -> returns partial document answer, flags `degraded=True, is_partial=True`.
  - Both fail -> returns non-grounded safe fallback error.

### `EvidenceMerger` (`app/analyst/merger.py`)
- Standardizes diverse evidence models into a single `list[UnifiedEvidence]`.
- Namespaces evidence identifiers:
  - `S1, S2, ...` for SQL query results, aggregates, and rows (tagged `is_calculated=True`).
  - `R1, R2, ...` for retrieved document chunks and headings (tagged `is_calculated=False`).
- Binds total evidence to the allocated budget (`ANALYST_MAX_EVIDENCE`).

### `ConflictDetector` (`app/analyst/conflicts.py`)
- Cross-references numerical metrics derived from SQL against numbers asserted in document chunks.
- Identifies discrepancies exceeding 5% divergence for comparable metrics.
- Mandates explicit disclosure in the synthesized response rather than arbitrary resolution.

### `AnalystProvenanceTracker` (`app/analyst/provenance.py`)
- Converts `UnifiedEvidence` items into sanitized `CitationItem` schemas.
- Filters citations strictly to valid cited identifiers.
- Redacts database connection strings and sensitive credentials.

---

## 3. Operational Limits & Resource Budgets

| Parameter | Configuration Setting | Default Value | Description |
|---|---|---|---|
| Request Timeout | `ANALYST_TOTAL_TIMEOUT_SECONDS` | 25.0 s | Hard deadline for end-to-end execution |
| SQL Branch Timeout | `ANALYST_SQL_TIMEOUT_SECONDS` | 10.0 s | Timeout for individual SQL agent branch |
| RAG Branch Timeout | `ANALYST_RAG_TIMEOUT_SECONDS` | 15.0 s | Timeout for individual RAG retrieval/generation |
| Max Branches | `ANALYST_MAX_BRANCHES` | 4 | Maximum allowed concurrent plan branches |
| Max Subqueries | `ANALYST_MAX_TOTAL_QUERIES` | 6 | Maximum subqueries dispatched across branches |
| Max Evidence | `ANALYST_MAX_EVIDENCE` | 20 | Maximum consolidated evidence items |
| Max Context Tokens | `ANALYST_MAX_CONTEXT_TOKENS` | 6000 | Upper token limit for synthesized context |

---

## 4. Multi-Tenant Isolation & RBAC

1. **Datasource Boundary**:
   Before an execution plan touches any database, `AnalystSecurityPolicy.validate_datasource_access` confirms that `datasource.organization_id == tenant.organization_id`. Any cross-tenant attempt raises `AnalystTenantMismatchError` (HTTP 403).
2. **Document Isolation**:
   The RAG branch strictly enforces `organization_id` filters in Qdrant and PostgreSQL metadata.
3. **RBAC Guard**:
   The endpoint `POST /api/v1/analyst/ask` requires `PERM_ANALYTICS_EXECUTE` (`analytics.execute`).

---

## 5. Telemetry & Observability

Every execution creates or updates the following database telemetry:
1. `AnalysisRun`: Persistent root execution record (`status="running"` -> `"completed"` / `"partial"`).
2. `AnalysisStep`: Step-level telemetry for planning, branch execution, and evidence merging.
3. `AuditLog`: Immutable audit trail under action `analyst_query`.
4. `UsageEvent`: Records request count and token expenditure.

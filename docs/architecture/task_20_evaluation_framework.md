# TASK 20 — Enterprise AI Evaluation & Quality Framework Architecture

## Overview

The **Enterprise AI Evaluation & Quality Framework** provides a reproducible, quantitative measurement subsystem for the Enterprise AI Intelligence Platform. It shifts the system from subjective assertions (*"the system works"*) to rigorous, mathematical validation (*"the system quantitatively proves how well it works"*).

Operating as an offline/evaluation harness over the unified analytical pipeline, it executes benchmark test cases directly against the production `AIAnalystService` orchestrator without duplicating business logic, without modifying runtime production behavior, and without inventing unmeasured metrics.

```text
Benchmark Test Cases (SQL, RAG, Hybrid, None)
                       ↓
               BenchmarkRunner
                       ↓
               AIAnalystService (Production Pipeline)
                       ↓
     [Execution Plan → SQL Agent / Hybrid RAG / Synthesis]
                       ↓
              Normalized Evidence & Output
                       ↓
              Evaluation Metrics Engine
     ├── Information Retrieval (Recall@K, MRR, nDCG@5)
     ├── RAG Faithfulness & Context Relevance
     ├── SQL Safety & Numeric Accuracy
     ├── Groundedness & Phantom Citation Detection
     ├── Hallucination Checks (Numbers, Dates, Percentages)
     └── Latency Percentiles (P50-P99) & Token Cost
                       ↓
          Deterministic / LLM Judge Scoring
                       ↓
         Evaluation Scorecard Generation
                       ↓
        Regression Detection vs Baseline Run
```

---

## 1. Architecture & Component Hierarchy

The evaluation layer resides within `app/evaluation/` and integrates with API v1 at `app/api/v1/evaluation.py`:

```text
app/evaluation/
├── __init__.py           # Consolidated package exports
├── config.py             # Operational thresholds, tolerances, and scorecard weights
├── exceptions.py         # Tenant isolation and evaluation domain exception hierarchy
├── models.py             # Domain dataclasses for metric suites, scorecards, and reports
├── schemas.py            # Pydantic request and response models for REST endpoints
├── dataset.py            # Dataset CRUD, immutable version snapshotting, and checksums
├── cases.py              # Test case creation, route validation, and dataset scoping
├── benchmark.py          # BenchmarkRunner executing against AIAnalystService
├── metrics/              # Deterministic mathematical measurement library
│   ├── __init__.py
│   ├── retrieval.py      # Recall@K, Precision@K, HitRate@K, MRR, nDCG@K
│   ├── rag.py            # Context Recall/Precision, Relevance, Faithfulness
│   ├── sql.py            # SQL Safety, Validity, Numeric Accuracy (tolerances)
│   ├── grounding.py      # Claim-to-evidence support (fully/partially/ungrounded)
│   ├── citation.py       # Precision, Recall, Coverage, Phantom Citation Rate
│   ├── hallucination.py  # Unsupported numbers, dates, percentages, citations
│   ├── latency.py        # Percentile calculations (p50, p75, p90, p95, p99)
│   └── cost.py           # Cost per query, per success, and per 1,000 cases
├── scorers/
│   ├── __init__.py
│   ├── deterministic.py  # Composite case-level scoring & pass/fail verdicts
│   └── llm_judge.py      # Abstract LLMJudgeProvider & DeterministicJudgeProvider
├── scorecard.py          # ScorecardGenerator aggregating quality/perf/cost scores
├── regression.py         # RegressionDetector comparing candidate against baseline runs
├── service.py            # EvaluationService facade managing transactions & audit logs
└── router.py             # FastAPI REST endpoints with RBAC & tenant dependencies
```

---

## 2. Evaluation Datasets & Versioning

### 2.1 Domain Model & Immutability
Benchmark datasets are represented by `EvaluationDataset` and `EvaluationDatasetVersion` tables in PostgreSQL:
- `id`: UUID primary key.
- `organization_id`: Strict tenant isolation.
- `name`, `description`, `language`: Dataset metadata.
- `version`: Monotonically increasing version integer.
- `status`: `"draft"`, `"active"`, or `"archived"`.

When an evaluation dataset's test cases are modified, `DatasetManager.snapshot_version()` calculates a deterministic SHA-256 checksum across all active test cases and commits an immutable snapshot row. Every benchmark run explicitly references both `dataset_id` and `dataset_version`, ensuring historical benchmark reproducibility.

---

## 3. Evaluation Cases & Modalities

Evaluation cases (`EvaluationCase`) define ground truth expectations across four analytical modalities:

1. **RAG Cases**:
   - `query`: E.g., *"What explains the decline in Q4 revenue?"*
   - `route_expected`: `"rag"`
   - `expected_documents`: Known document names or IDs.
   - `expected_citations`: Ground-truth citation markers (`["R1"]`).
   - `expected_answer`: Reference factual answer.

2. **SQL Cases**:
   - `query`: E.g., *"What was total revenue in Q4?"*
   - `route_expected`: `"sql"`
   - `datasource_id`: Targeted relational database source.
   - `expected_metrics`: Numeric dictionary, e.g. `{"revenue": 120000000}`.
   - `expected_sql_semantics`: Semantic clause tokens for structural validation.

3. **Hybrid Cases**:
   - `query`: E.g., *"Compare Q4 revenue with annual report findings"*
   - `route_expected`: `"hybrid"`
   - Evaluates SQL numerical precision, unstructured context retrieval, cross-modal evidence synthesis, and conflict detection.

4. **None / Out-of-Domain Cases**:
   - Validates proper rejection of unsupported or unanswerable queries without hallucinations.

---

## 4. Evaluation Metrics Engine

All metrics are calculated deterministically without reliance on nondeterministic remote LLMs unless explicitly invoked via the `LLMJudgeProvider` abstraction.

### 4.1 Information Retrieval (IR) Metrics
- **Recall@K**: Proportion of relevant documents/chunks retrieved in the top $K$ candidates ($K \in \{1, 3, 5, 10\}$).
- **Precision@K**: Proportion of top $K$ retrieved items that are relevant.
- **HitRate@K**: Binary indicator ($1.0$ or $0.0$) indicating whether at least one relevant item exists in top $K$.
- **Mean Reciprocal Rank (MRR)**: $1 / \text{rank}$ of the first relevant document.
- **Normalized Discounted Cumulative Gain (nDCG@K)**: Logarithmic position-weighted ranking quality.

### 4.2 RAG Metrics
- **Context Recall**: Ratio of ground-truth factual assertions present in retrieved context excerpts.
- **Context Precision**: Ratio of retrieved context chunks matching designated relevant passages.
- **Answer Relevance**: Lexical and semantic token alignment between query intent and synthesized answer.
- **Faithfulness**: Ratio of claims in the generated response directly corroborated by retrieved context.

### 4.3 SQL Metrics
- **SQL Safety**: Absolute binary check prohibiting DDL/DML injection keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `GRANT`, `REVOKE`) and comment-based injection attacks (`--`, `/* */`).
- **SQL Validity**: Execution success indicator verifying zero database runtime errors.
- **Semantic Equivalence**: Token-based containment check verifying required tables, columns, and aggregation functions.
- **Numeric Accuracy**: Relative difference calculation with configurable tolerance ratios:
  $$\text{diff\_ratio} = \frac{|\text{actual} - \text{expected}|}{\max(|\text{expected}|, |\text{actual}|)}$$
  Supports `exact` ($0\%$), `0.1%`, `1%`, and `5%` relative error boundaries.

### 4.4 Grounding & Citation Accuracy
- **Citation Precision**: Proportion of citations referencing existing, verified evidence IDs.
- **Citation Recall**: Proportion of expected ground-truth evidence items cited.
- **Citation Coverage**: Proportion of answer claims containing formal evidence citations.
- **Phantom Citation Rate**: Proportion of citations referencing non-existent or fabricated sources ($[X99]$).
- **Groundedness Classification**: Categorizes answers into `"fully_grounded"` ($\ge 0.8$), `"partially_grounded"`, or `"ungrounded"`.

### 4.5 Hallucination Detection
Deterministic pattern matching detecting:
- `unsupported_numeric_claim`: Numeric figures in the answer not corroborated by evidence.
- `phantom_citation`: Fabricated bracket citations ($[Ghost1]$).
- `unsupported_percentage`: Uncorroborated percentage claims.
- `unsupported_date`: Unverified year or quarter references ($Q4$, $2025$).

### 4.6 Latency & Cost Metrics
- **Latency Percentiles**: Computed using linear interpolation: $P50$, $P75$, $P90$, $P95$, $P99$.
- **Token & Cost Accounting**: Cost per case, cost per successful query, and cost per 1,000 queries based on actual token usage metadata.

---

## 5. Scorecards & Regression Detection

### 5.1 Evaluation Scorecard
Aggregates case-level results into distinct, non-masking score categories:
- **Quality Score**: Weighted combination of route accuracy, retrieval recall, citation precision, groundedness, SQL accuracy, and hallucination penalty.
- **Performance Score**: Latency score derived from $P95$ execution time.
- **Cost Score**: Cost efficiency score based on query token consumption.
- **Overall Score**: Weighted composite of quality, performance, and cost.

### 5.2 Regression Detection
`RegressionDetector` executes comparative diffs between a candidate benchmark run and an approved baseline run:
- Identifies newly failing cases that previously passed.
- Flags degradations exceeding configurable thresholds:
  - `max_allowed_quality_regression`: $5\%$ drop $\rightarrow$ `FAIL`.
  - `max_allowed_retrieval_regression`: $5\%$ drop in Recall@5 $\rightarrow$ `FAIL`.
  - `max_allowed_grounding_regression`: $3\%$ drop in Groundedness $\rightarrow$ `FAIL`.
  - `max_allowed_latency_increase_ratio`: $20\%$ increase $\rightarrow$ `WARNING` / `FAIL`.

---

## 6. Security, Tenant Isolation & RBAC

### 6.1 Multi-Tenant Isolation
Every evaluation entity (`EvaluationDataset`, `EvaluationDatasetVersion`, `EvaluationCase`, `EvaluationRun`, `EvaluationCaseResult`) contains an indexed `organization_id` foreign key. Cross-tenant access is prohibited at the database query and service layer; attempts to access foreign datasets return `403 Forbidden` or `404 Not Found`.

### 6.2 Granular RBAC Permissions
Four dedicated permissions are enforced across all evaluation endpoints:
- `evaluation.read`: Permitted for `Admin`, `Analyst`, and `Viewer` (read-only inspection of datasets, cases, runs, and scorecards).
- `evaluation.create`: Permitted for `Admin` and `Analyst` (dataset and case creation).
- `evaluation.run`: Permitted for `Admin` and `Analyst` (triggering benchmark runs).
- `evaluation.compare`: Permitted for `Admin` and `Analyst` (regression comparison).

`Viewer` users are strictly blocked from triggering runs or modifying datasets.

### 6.3 Audit Logging
All lifecycle mutations persist structured audit entries in the `audit_logs` table:
- `evaluation.dataset_created`
- `evaluation.case_created`
- `evaluation.run_completed`
- `evaluation.compared`

---

## 7. REST API Endpoints

Mounted under `/api/v1/evaluation`:

| Method | Endpoint | Description | Required Permission |
|---|---|---|---|
| `POST` | `/api/v1/evaluation/datasets` | Create benchmark dataset | `evaluation.create` |
| `GET` | `/api/v1/evaluation/datasets` | List tenant datasets | `evaluation.read` |
| `POST` | `/api/v1/evaluation/datasets/{id}/cases` | Add benchmark test case | `evaluation.create` |
| `GET` | `/api/v1/evaluation/datasets/{id}/cases` | List test cases in dataset | `evaluation.read` |
| `POST` | `/api/v1/evaluation/runs` | Start benchmark run | `evaluation.run` |
| `GET` | `/api/v1/evaluation/runs/{run_id}` | Get benchmark run details | `evaluation.read` |
| `GET` | `/api/v1/evaluation/runs/{run_id}/results` | Get case-level results | `evaluation.read` |
| `GET` | `/api/v1/evaluation/runs/{run_id}/scorecard` | Get run scorecard | `evaluation.read` |
| `POST` | `/api/v1/evaluation/runs/{run_id}/compare` | Compare candidate run to baseline | `evaluation.compare` |

---

## 8. Limitations & Explicit Exclusions

In accordance with architectural boundaries:
- **No Autonomous Agent Loops**: The evaluator executes fixed, deterministic benchmark runs; it does not introduce autonomous loop agents or self-prompting feedback loops.
- **No Web Search**: All evaluation operates exclusively against local tenant datasets and verified SQL databases.
- **No Model Fine-Tuning**: The framework evaluates pre-existing models and prompts; it does not perform parameter fine-tuning.
- **No Production Answer Interference**: Evaluators and LLM judges operate out-of-band; they do not alter runtime production query paths.

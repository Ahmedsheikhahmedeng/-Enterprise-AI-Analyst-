# TASK 15 — Query Understanding, Rewriting & Multi-Query Retrieval Architecture

## 1. Overview & Motivation

In the Enterprise AI Analyst platform, incoming user queries are frequently conversational, terse, underspecified, or multi-faceted (e.g. comparing metrics across two fiscal years or asking about cause-and-effect). If passed raw to dense or sparse retrieval, such queries can degrade recall or miss entire aspects of a comparison.

**Task 15** establishes an intelligent **Query Understanding, Rewriting & Multi-Query Retrieval** layer prior to Hybrid Retrieval and Cross-Encoder Reranking:

```text
User Query
     ↓
Query Safety & Length Validation
     ↓
Multilingual Language Detection (Arabic / Turkish / English / Mixed)
     ↓
Query Normalization (Unicode NFC, whitespace, punctuation, entity preservation)
     ↓
Intent Classification & Entity Extraction (Explicit vs Inferred)
     ↓
Query Rewriting (Search-oriented, no hallucinations)
     ↓
Optional Query Expansion (Domain synonyms in Arabic, Turkish, English)
     ↓
Optional Query Decomposition (Multi-part questions broken into sub-queries)
     ↓
Query Deduplication & Complexity Routing
     ↓
SearchPlan Construction (Budget & Filter Hints)
     ↓
Multi-Query Hybrid Retrieval (Concurrent Dense + Sparse BM25)
     ↓
Cross-Query RRF Fusion & Candidate Deduplication
     ↓
Cross-Encoder Reranking
     ↓
PostgreSQL Parent Hydration (Zero N+1)
     ↓
Final Enriched Top-K Chunks
```

---

## 2. Component Architecture

The query understanding subsystem resides under `app/query/`:

```text
app/query/
├── __init__.py                # Module exports (models, exceptions, services)
├── config.py                  # QueryUnderstandingConfig dataclass & settings adapter
├── exceptions.py              # Domain error hierarchy
├── models.py                  # QueryIntent, ExtractedEntity, SearchPlan, MultiQueryResult
├── schemas.py                 # Pydantic schemas for REST API
├── normalization.py           # Safe, multilingual query normalizer
├── language.py                # Deterministic multilingual language detector
├── safety.py                  # Bounds validation & prompt injection mitigation
├── intent.py                  # Enterprise intent classifier
├── entities.py                # Entity extraction & filter separation
├── rewrite.py                 # Search-oriented query rewriter
├── expansion.py               # Domain synonym query expander
├── decomposition.py           # Multi-part & comparison query decomposer
├── deduplication.py           # Token-overlap query deduplicator
├── service.py                 # QueryUnderstandingService (orchestrator)
├── multi_retrieval.py         # MultiQueryRetrievalService (Cross-Query RRF)
└── providers/
    ├── __init__.py            # Provider exports
    ├── base.py                # QueryUnderstandingProvider Protocol
    ├── deterministic.py       # Rule-based offline provider
    ├── llm.py                 # LLM provider with strict schema validation
    └── factory.py             # Provider factory
```

---

## 3. Query Object & Original Query Immutability

The core contract is built around `QueryAnalysis` and `SearchPlan`:
* **Original Query Immutability**: The user's input `original_query` is strictly preserved and never mutated or overwritten.
* `primary_query`: The search-optimized formulation if confidence exceeds threshold, otherwise the normalized query.
* `alternative_queries`: Bounded synonym expansions.
* `sub_queries`: Bounded decomposed atomic questions for comparative or compound queries.

---

## 4. Query Normalization & Language Detection

### 4.1 Safe Normalization
* Standardizes text via Unicode NFC.
* Collapses excessive whitespace and control characters.
* Crucially preserves business identifiers (`XJ-4927`), fiscal quarters (`Q1`-`Q4`), dates (`2024-10-12`), currencies (`$120M`), and percentages (`15.5%`).

### 4.2 Multilingual Detection
Supports:
* **Arabic (`ar`)**: Detects Arabic script ranges (`\u0600-\u06FF`) and key financial cue words (`إيرادات`, `هامش التشغيل`, etc.).
* **Turkish (`tr`)**: Detects Turkish-specific orthography (`ç`, `ğ`, `ı`, `ö`, `ş`, `ü`, `İ`) and domain lexicon.
* **English (`en`)**: Detects Latin lexicon and business terms.
* **Mixed (`mixed`)**: Detects multilingual code-switching queries (e.g. `"Q4 gelir analysis"`, `"Revenue neden düştü?"`).

---

## 5. Intent Classification & Entity Extraction

### 5.1 Intent Taxonomy
Queries are categorized into enterprise search intents:
1. `factual_lookup`: Direct inquiries regarding metrics or states.
2. `comparison`: Inquiries contrasting two entities or periods (triggers decomposition).
3. `trend_analysis`: Evolution of metrics across time.
4. `definition`: Terminology or conceptual explanations.
5. `summarization`: Document or section synthesis requests.
6. `explanation`: Causal inquiries ("why did revenue decline?").
7. `aggregation`: Numerical totals, averages, or extrema.
8. `filter_lookup`: Document or code specific inquiries.
9. `multi_part`: Compound multi-clause questions (triggers decomposition).
10. `unknown`: Unclassified queries fallback to raw retrieval.

### 5.2 Entity Extraction & Filter Separation
* Extracts: dates, years, quarters, currency, percentages, metrics, product codes, and corporate identifiers.
* **Explicit vs. Inferred**: Explicit items directly match query tokens; inferred items are model-derived hints.
* **Hard vs. Soft Filters**:
  - `hard_filters`: Confirmed explicit constraints (e.g. `code="XJ-4927"`).
  - `soft_filters`: Thematic hints (e.g. `metric="revenue"`).
  - **Security Rule**: Inferred entities never become hard filters that could inadvertently drop documents or bypass permissions.

---

## 6. Query Rewriting, Expansion & Decomposition

### 6.1 Query Rewriting
* Eliminates conversational filler (e.g. `"Can you tell me about the operating margin"` $\rightarrow$ `"operating margin"`).
* Expands terse single-word queries (e.g. `"margin?"` $\rightarrow$ `"operating margin operating profitability margin percentage"`).
* Avoids hallucinating facts or unmentioned organizations.

### 6.2 Query Expansion
* Injects domain-specific synonyms in Arabic, Turkish, and English.
* Bounded by `QUERY_MAX_ALTERNATIVE_QUERIES = 3`.

### 6.3 Query Decomposition
* Splits compound questions into targeted sub-queries.
* Example: `"Compare revenue in 2024 and 2025"`
  - Subquery 1: `"revenue 2024"`
  - Subquery 2: `"revenue 2025"`
* Bounded by `QUERY_MAX_SUBQUERIES = 3`.

---

## 7. Deduplication & Resource Budgets

To prevent query explosion and denial-of-service:
* `QueryDeduplicator` filters out queries with Jaccard token overlap $\ge 0.85$.
* Hard ceiling on total queries planned: `QUERY_MAX_TOTAL_QUERIES = 5`.
* Latency budget: `QUERY_UNDERSTANDING_TIMEOUT_SECONDS = 3.0s`.

---

## 8. Multi-Query Retrieval & Cross-Query RRF Fusion

When a `SearchPlan` produces multiple queries ($Q_1, Q_2, \dots, Q_m$):
1. **Parallel Execution**: All query variants run concurrent hybrid searches (Dense + Sparse BM25) with `rerank=False` and `include_parent=False`.
2. **Cross-Query RRF Fusion**:
   $$\text{CrossQueryScore}(c) = \sum_{j=1}^{m} \frac{w_j}{60 + \text{rank}(c, Q_j)}$$
   where $w_{\text{primary}} = 1.0$, $w_{\text{subquery}} = 0.9$, $w_{\text{alternative}} = 0.8$.
3. **Deduplication**: Candidates retrieved across multiple variants are merged by `chunk_id`.
4. **Cross-Encoder Reranking**: The deduplicated candidate pool is scored once by the cross-encoder against `plan.original_query`.
5. **Post-Rerank Parent Hydration**: Top-K chunks are sliced and their parent chunks are hydrated in a single batch query (Zero N+1).

---

## 9. Safety, Prompt Injection & Privacy

* **Prompt Injection**: Input queries are wrapped in strict tags `<user_query>` and adversarial phrases (`"ignore previous instructions"`, `"system prompt"`) are neutralized.
* **No Chain-of-Thought**: Any model reasoning is discarded and never persisted in database, logs, or API responses.
* **Tenant Isolation**: Cache keys are scoped by `(organization_id, query_hash)`.

---

## 10. REST API Integration

### 10.1 Dedicated Analysis Endpoint
`POST /api/v1/query/analyze`:
```json
{
  "query": "Compare 2024 and 2025 revenue for ACME under Project XJ-4927",
  "enable_rewrite": true,
  "enable_expansion": true,
  "enable_decomposition": true
}
```

### 10.2 Hybrid Search with Query Planning
`POST /api/v1/retrieval/hybrid-search`:
```json
{
  "query": "Compare revenue in 2024 and 2025",
  "top_k": 10,
  "enable_query_understanding": true,
  "enable_query_decomposition": true,
  "rerank": true
}
```

---

## 11. Known Limitations

1. **Deterministic Mode Limitations**: The rule-based provider uses regex and lexical dictionaries. It covers financial and enterprise domains well, but cannot perform arbitrary zero-shot generalization like large frontier models.
2. **LLM Latency Trade-off**: When using external LLM providers, network latency adds 300–800ms to query planning. The deterministic offline mode provides sub-millisecond execution (< 1ms).

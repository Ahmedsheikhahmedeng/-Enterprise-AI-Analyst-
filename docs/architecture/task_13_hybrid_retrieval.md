# TASK 13 — Advanced Hybrid Retrieval & Reciprocal Rank Fusion (RRF) Architecture

## 1. Executive Summary

Task 13 upgrades the *Enterprise AI Analyst* retrieval subsystem from single-modality dense semantic search (Task 12) to an enterprise-grade **Hybrid Retrieval** system:

$$\text{Hybrid Retrieval} = \text{Dense Semantic Retrieval} + \text{Sparse BM25 Lexical Retrieval} + \text{Reciprocal Rank Fusion (RRF)}$$

The upgraded pipeline combines the broad conceptual understanding of dense embeddings with the exact lexical precision of BM25. It excels at matching exact product names, IDs, numbers, abbreviations, and enterprise jargon while supporting Arabic, Turkish, English, and mixed-language enterprise documents under strict multi-tenant isolation.

---

## 2. High-Level Pipeline Architecture

```
                                 User Query
                                      │
                   ┌──────────────────┴──────────────────┐
                   ▼                                     ▼
            Query Embedding                     Sparse Tokenization & IDF
          (DenseRetrievalService)                (MultilingualSparseAnalyzer)
                   │                                     │
                   ▼                                     ▼
        Qdrant Dense Vector Search             Qdrant Sparse Vector Search
       (Cosine Similarity Search)                    (BM25 Dot Product)
                   │                                     │
                   └──────────────────┬──────────────────┘
                                      ▼
                        Candidate Generation & Pools
                        - Dense Candidates:  k_dense (e.g. 50)
                        - Sparse Candidates: k_sparse (e.g. 50)
                                      │
                                      ▼
                        Reciprocal Rank Fusion (RRF)
                        - Candidate Deduplication
                        - 1 / (RRF_K + rank)
                        - Individual Score & Rank Tracking
                                      │
                                      ▼
                          Top-K Fused Candidates
                                      │
                                      ▼
                        Post-Fusion Batch Hydration
                        - Single SQL Query (get_by_ids)
                        - Optional Parent Chunk Context
                        - Strictly 0 N+1 Queries
                                      │
                                      ▼
                         Final Hybrid Results Model
```

---

## 3. Sparse Retrieval & BM25 Formulation

### 3.1 Okapi BM25 in Vector Space
The standard Okapi BM25 scoring formula is:

$$\text{score}(D, Q) = \sum_{q \in Q} IDF(q) \cdot \frac{f(q, D) \cdot (k_1 + 1)}{f(q, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{avgdl}\right)}$$

Where:
- $k_1 = 1.2$ (configurable via `BM25_K1`): Controls term frequency saturation.
- $b = 0.75$ (configurable via `BM25_B`): Controls document length penalization.
- $avgdl$: Average document length across the tenant's corpus.

### 3.2 Dual Vector Representation in Qdrant
Rather than maintaining an out-of-process auxiliary index, BM25 is projected natively into Qdrant sparse vectors:
1. **Document Chunk Sparse Vector**:
   For each unique token $t \in D$, the document sparse vector weight is:
   $$W_{doc}(t) = \frac{f(t, D) \cdot (k_1 + 1)}{f(t, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{avgdl}\right)}$$
2. **Query Sparse Vector**:
   For each unique query token $q \in Q$, the query sparse vector weight is Robertson-Spärck Jones smoothed IDF:
   $$W_{query}(q) = \ln\left(1 + \frac{N - n(q) + 0.5}{n(q) + 0.5}\right) \cdot f(q, Q)$$
3. **Dot Product Equivalence**:
   The inner product computed by Qdrant over these sparse vectors is mathematically identical to the exact Okapi BM25 score:
   $$\langle W_{query}, W_{doc} \rangle = \sum_{q \in Q \cap D} W_{query}(q) \cdot W_{doc}(q) \equiv \text{score}(D, Q)$$

---

## 4. Multilingual Lexical Analyzer

The `MultilingualSparseAnalyzer` handles tokenization and linguistic normalization across all target languages:

### 4.1 Turkish Locale Handling
- Standard Python `.lower()` corrupts Turkish dotted/dotless `I`.
- Custom `turkish_lower()` accurately maps:
  - Capital dotted `İ` (U+0130) $\rightarrow$ `i` (U+0069)
  - Capital dotless `I` (U+0049) $\rightarrow$ `ı` (U+0131)
  - Preserves Turkish characters `ş`, `ğ`, `ç`, `ö`, `ü`.

### 4.2 Arabic Normalization
- Standardizes letter shapes:
  - Hamza variants (`أ`, `إ`, `آ`) $\rightarrow$ `ا`
  - Taa Marbuta (`ة`) $\rightarrow$ `ه`
  - Alef Maksura (`ى`) $\rightarrow$ `ي`
- Tashkeel diacritics (`\u064B-\u065F`, `\u0670`) are stripped so vocalized text matches non-vocalized queries (e.g. `أَرْبَاح` matches `أرباح`).
- Converts Eastern Arabic-Indic digits (`٠-٩`) to Western ASCII standard (`0-9`).

### 4.3 Numbers, Codes, and Enterprise Identifiers
- Enterprise search relies heavily on serial numbers, fiscal codes, and metrics.
- Tokenizer pattern `[\w]+(?:[-_/\.][\w]+)*%?` preserves:
  - Financial quarters: `Q4`, `H1`
  - Years: `2024`, `2025`
  - Percentages: `15%`, `2.5%`
  - Product / Model IDs: `XJ-4927`, `PROD-998`, `EUR-500`

### 4.4 Deterministic Token Hashing & Versioning
- Each token string is deterministically mapped to a stable positive 31-bit unsigned integer ID:
  $$\text{token\_id} = \text{CRC32}(\text{version} + ":" + \text{token}) \ \& \ \text{0x7FFFFFFF}$$
- Version tag (`bm25-v1`) guarantees immutable indexing and query compatibility.
- **Collision & Distribution Analysis**: CRC32 masked to 31 bits provides uniform dispersion across 2.14 billion integer bins. In the rare event of a token collision, term frequencies merge into the same sparse index (the standard feature-hashing trick in sparse retrieval models like SPLADE/FastBM25), maintaining dot-product operations without runtime errors. For ultra-massive corpora exceeding 100M unique terms, a 63-bit integer hash or centralized PostgreSQL vocabulary table can be introduced under version `bm25-v2`.

---

## 5. Multi-Tenant Corpus Statistics

Corpus statistics ($N$, $avgdl$, and term frequencies $n(q)$) are managed by `TenantCorpusStatsManager`.
- **Strict Isolation**: Tenant A's documents never enter or influence Tenant B's corpus statistics.
- **Thread Safety**: Backed by thread locks for concurrent async operations within the process.
- **Cold-Start Guard**: If a tenant has zero indexed documents, defaults to $N=1, avgdl=1.0$ to prevent division-by-zero or negative IDF values.
- **Multi-Process Architecture Limitation**: The default in-memory `TenantCorpusStatsManager` stores corpus stats inside the current OS worker process. If multiple worker processes (e.g. multi-worker Uvicorn/Gunicorn) serve queries before indexing occurs in that specific process, IDF gracefully defaults to smoothed baseline ($1.0$). For distributed multi-node production deployments, stats can be synchronized using Redis or PostgreSQL aggregates (`SELECT count(*)...`).

---

## 6. Reciprocal Rank Fusion (RRF)

### 6.1 Formula
Candidates from dense and sparse retrieval are merged strictly via their ordinal ranks:

$$RRF\_score(d) = \sum_{m \in \{\text{dense}, \text{sparse}\}} \frac{1}{k + rank_m(d)}$$

Where $k = 60$ (configurable via `HYBRID_RRF_K`).

### 6.2 Raw Score Separation Guarantee
- **CRITICAL DESIGN RULE**: Raw dense cosine similarities and raw BM25 lexical scores are **NEVER** added together directly ($dense + sparse$).
- Cosine distance and BM25 have fundamentally incompatible probability distributions and scales.
- RRF normalizes across modalities purely via rank positions ($1, 2, 3, \dots$).

### 6.3 Explainability Metadata
Each retrieved chunk retains transparent provenance:
- `rank`: Final fused position (1, 2, 3...)
- `rrf_score`: Fused RRF score
- `dense_rank`: Rank in dense candidate list (or `None`)
- `dense_score`: Raw cosine similarity score (or `None`)
- `sparse_rank`: Rank in sparse BM25 candidate list (or `None`)
- `sparse_score`: Raw BM25 score (or `None`)

---

## 7. Performance & Concurrency

### 7.1 Parallel Retrieval
- Dense and sparse search tasks execute concurrently via `asyncio.gather(_retrieve_dense(), _retrieve_sparse(), return_exceptions=True)`.
- Total search latency approaches $\max(\text{latency}_{dense}, \text{latency}_{sparse}) + \text{latency}_{fusion} + \text{latency}_{hydration}$ rather than sequential addition.

### 7.2 Timeout Coordination & Partial Failure Degradation
- Bounded by a unified request budget (`RETRIEVAL_TIMEOUT_SECONDS = 15.0s`).
- If dense search fails but sparse succeeds (or vice-versa), the system operates in graceful degradation mode:
  - `retrieval_mode = "sparse_fallback"` or `"dense_fallback"`
  - `diagnostics.is_degraded = True`
  - `diagnostics.degradation_reason = "..."`

---

## 8. Post-Fusion Zero N+1 Hydration

Hydration occurs **strictly after** RRF fusion on the final top-$K$ candidates:
1. `chunk_repository.get_by_ids(session, ids=final_top_k_ids, organization_id=org_id)` $\rightarrow$ 1 SQL query.
2. If `include_parent=True`:
   `chunk_repository.get_by_ids(session, ids=parent_ids, organization_id=org_id)` $\rightarrow$ 1 SQL query.
3. Total database queries: At most 2, regardless of candidate pool size ($K_{dense}=50, K_{sparse}=50$).

---

## 9. API Specification

### Endpoint
```http
POST /api/v1/retrieval/hybrid-search
Authorization: Bearer <JWT>
Content-Type: application/json
```

### Request Payload
```json
{
  "query": "What was the revenue in Q4 2025?",
  "top_k": 10,
  "dense_candidate_k": 50,
  "sparse_candidate_k": 50,
  "rrf_k": 60,
  "document_id": null,
  "chunk_type": null,
  "page_number": null,
  "section": null,
  "score_threshold": null,
  "include_parent": true
}
```

### Response Payload
```json
{
  "query": "What was the revenue in Q4 2025?",
  "retrieval_mode": "hybrid",
  "total_results": 1,
  "results": [
    {
      "rank": 1,
      "chunk_id": "8e3b4a21-...",
      "document_id": "c1f7b820-...",
      "rrf_score": 0.032522,
      "dense_score": 0.892,
      "dense_rank": 2,
      "sparse_score": 15.42,
      "sparse_rank": 1,
      "text": "Consolidated revenue in Q4 2025 reached $500M...",
      "chunk_index": 0,
      "chunk_type": "paragraph",
      "token_count": 8,
      "character_count": 48,
      "page_number": 1,
      "page_end": null,
      "section": null,
      "heading_hierarchy": [],
      "parent_chunk_id": null,
      "parent_text": null,
      "metadata": {}
    }
  ],
  "diagnostics": {
    "collection_name": "enterprise_ai__local__bge_small__384__1_0_0",
    "dense_candidate_count": 20,
    "sparse_candidate_count": 20,
    "merged_candidate_count": 25,
    "final_result_count": 1,
    "rrf_k": 60,
    "dense_candidate_k": 50,
    "sparse_candidate_k": 50,
    "final_top_k": 10,
    "is_degraded": false,
    "degradation_reason": null,
    "latency": {
      "dense_ms": 14.2,
      "sparse_ms": 8.5,
      "fusion_ms": 0.3,
      "hydration_ms": 1.5,
      "total_ms": 24.5
    }
  }
}
```

---

## 10. Scope Boundary Verification

| Component | Status | Implementation Details |
| :--- | :--- | :--- |
| **Dense Retrieval** | **IMPLEMENTED** | Reused directly from Task 12 with candidate retrieval optimization |
| **Sparse Retrieval** | **IMPLEMENTED** | Multilingual lexical tokenizer, Okapi BM25 scoring |
| **BM25 Scoring** | **IMPLEMENTED** | Configurable $k_1, b$, Robertson-Spärck Jones smoothed IDF |
| **Hybrid Retrieval** | **IMPLEMENTED** | Concurrent execution via `asyncio.gather` with timeout deadline |
| **Reciprocal Rank Fusion** | **IMPLEMENTED** | Ordinal rank fusion, candidate deduplication, explainable tracking |
| **Cross-Encoder Reranking**| **NOT IMPLEMENTED** | Strictly deferred to future tasks |
| **Query Rewriting / Expansion** | **NOT IMPLEMENTED** | Strictly deferred to future tasks |
| **Query Decomposition** | **NOT IMPLEMENTED** | Strictly deferred to future tasks |
| **RAG Answer Generation** | **NOT IMPLEMENTED** | Strictly deferred to future tasks |
| **LLM Agents** | **NOT IMPLEMENTED** | Strictly deferred to future tasks |

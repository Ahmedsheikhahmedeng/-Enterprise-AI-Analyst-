# TASK 14 — Cross-Encoder Reranking Architecture

## 1. Overview & Motivation

In the Enterprise AI Analyst platform, retrieving relevant chunks via Hybrid Retrieval (Dense + Sparse BM25 fused with RRF) yields high recall across semantic queries, exact keywords, SKU codes, and multilingual text. However, bi-encoder dense embeddings (cosine similarity) and lexical BM25 evaluate query and chunk representations independently. They cannot model complex cross-attention or fine-grained token-level interactions between query intent and candidate text.

Cross-Encoder Reranking introduces a dedicated cross-attention scoring layer on top of RRF candidate pools. By scoring `(query, candidate_chunk)` pairs jointly, the cross-encoder evaluates direct relevance, penalizes keyword stuffing, rewards exact context answering, and reorganizes the top candidates before final answer synthesis or presentation.

```text
Natural Language Query
        │
        ├─────────────────────────────┐
        ▼                             ▼
Dense Retrieval (Vector)       Sparse Retrieval (BM25)
        │                             │
        └──────────────┬──────────────┘
                       ▼
            Reciprocal Rank Fusion (RRF)
                       ▼
             Candidate Pool (K=50)
                       ▼
          Multi-Tenant Isolation Check
                       ▼
        Cross-Encoder Reranking (Batched)
                       ▼
            Deterministic Top-K Sort
                       ▼
     PostgreSQL Parent Chunk Hydration (Zero N+1)
                       ▼
          Final Hybrid Retried Chunks (K=10)
```

---

## 2. Component Architecture

The reranking subsystem resides under `app/reranking/`:

```text
app/reranking/
├── __init__.py                # Module exports (service, models, exceptions)
├── config.py                  # RerankerConfig dataclass & settings adapter
├── exceptions.py              # Domain error hierarchy
├── models.py                  # RerankPair, RerankedCandidate, RerankingDiagnostics, etc.
├── batching.py                # Chunk partitioning & batch slicing
├── validators.py              # Query validation, tenant boundary, input truncation
├── service.py                 # CrossEncoderRerankingService (orchestrator)
└── providers/
    ├── __init__.py            # Provider exports
    ├── base.py                # RerankerProvider Protocol interface
    ├── local.py               # LocalDeterministicCrossEncoderProvider
    ├── sentence_transformers.py # SentenceTransformers CrossEncoder wrapper
    └── factory.py             # RerankerProviderFactory
```

---

## 3. Provider Abstraction & Model Selection

### 3.1 Protocol Interface
`RerankerProvider` defines a strict protocol decoupling PyTorch/HuggingFace/SentenceTransformers from the service:

```python
class RerankerProvider(Protocol):
    provider_name: str
    model_name: str
    version: str

    async def score_pairs(
        self,
        pairs: Sequence[tuple[str, str]],
    ) -> list[float]: ...

    async def health_check(self) -> bool: ...
```

### 3.2 Implemented Providers
1. **`LocalDeterministicCrossEncoderProvider`** (`local`):
   - In-memory deterministic provider utilizing multilingual n-gram tokenization, inverted index frequency analysis with strict diminishing returns (`1.0 + 0.2 * log(freq)` to mitigate keyword stuffing), sequential cross-attention window proximity, and logistic calibration.
   - Requires zero external weights or GPU downloads, ensuring robust, deterministic CI/CD execution across macOS, Linux, and Windows.
2. **`SentenceTransformersRerankerProvider`** (`sentence_transformers`):
   - Wraps HuggingFace `sentence-transformers.CrossEncoder`.
   - Supports neural models such as `cross-encoder/ms-marco-MiniLM-L-6-v2` or multilingual cross-encoders like `BAAI/bge-reranker-large` / `amberoad/bert-multilingual-passage-reranking`.
   - Offloads blocking tensor operations to `asyncio.to_thread`.
3. **`RerankerProviderFactory`**:
   - Manages provider instantiation and runtime dependency validation.

---

## 4. Candidate Pool & Sizing Strategy

To balance retrieval recall, precision, and latency, the retrieval pipeline adheres to a tiered candidate sizing strategy:

| Phase | Parameter | Default Value | Description |
|---|---|---|---|
| Dense Retrieval | `DENSE_CANDIDATE_K` | 50 | Candidates retrieved from Qdrant vector index |
| Sparse Retrieval | `SPARSE_CANDIDATE_K` | 50 | Candidates retrieved from in-memory BM25 index |
| RRF Fusion | `RRF_CANDIDATE_K` | 50 | Combined deduplicated candidates merged via RRF |
| Candidate Guard | `RERANKER_MAX_CANDIDATES` | 50 | Maximum allowed candidate pool passed to reranker |
| Final Top-K | `RERANKER_FINAL_K` / `top_k` | 10 | Final hydrated chunks returned to caller |

Clients can request up to `rerank_candidates <= RERANKER_MAX_CANDIDATES` (default 50). Requests specifying higher values are clamped or rejected by `RerankerValidator`.

---

## 5. Batching, Concurrency & Device Management

### 5.1 Batching
Inference over 50 candidates is processed in discrete batches (default `RERANKER_BATCH_SIZE = 16`), resulting in batches of [16, 16, 18]. This avoids PyTorch memory spikes and OOM conditions on memory-constrained devices.

### 5.2 Controlled Concurrency
Concurrency is strictly governed by an asynchronous `asyncio.Semaphore(max_concurrent_batches)`:
- Default `RERANKER_MAX_CONCURRENT_BATCHES = 1`.
- Serializes heavy GPU/CPU tensor forward passes to prevent CPU starvation and thread contention.

### 5.3 Hardware Awareness (CPU / GPU / MPS)
Device resolution is dynamic:
- `auto`: Resolves `cuda` if PyTorch detects CUDA, `mps` on Apple Silicon macOS devices, and falls back to `cpu`.
- Explicit: Allows administrator configuration via `RERANKER_DEVICE=cpu|cuda|mps`.

---

## 6. Input Limits & Safety Truncation

- Query length is bounded (`MAX_QUERY_LENGTH = 1000` chars) and cannot be blank.
- Candidate text is validated against `RERANKER_MAX_INPUT_TOKENS` (default 512 tokens).
- Chunks produced in Task 9 are already bounded to $\le 512$ tokens. However, as a deterministic safety guard, `RerankerValidator.truncate_text_if_needed` applies deterministic head/tail preservation if chunk text exceeds bounds, preventing silent truncation or model failure.
- Prompt injection attempts inside chunk text (`"Ignore previous instructions..."`) are treated purely as inert text strings for cross-encoder inference.

---

## 7. Score Semantics & Result Provenance

The system maintains strict semantic separation across all scoring and ranking layers:

| Field | Source | Range | Semantic Meaning |
|---|---|---|---|
| `dense_score` | Qdrant | $[-1.0, 1.0]$ | Cosine similarity from bi-encoder embedding |
| `dense_rank` | Qdrant | $[1, K]$ | Rank position within dense candidate list |
| `sparse_score` | BM25 | $\ge 0.0$ | Okapi BM25 lexical term match score |
| `sparse_rank` | BM25 | $[1, K]$ | Rank position within sparse candidate list |
| `rrf_score` | RRF Fusion | $(0.0, 1.0]$ | Reciprocal Rank Fusion score $\sum \frac{1}{60 + \text{rank}}$ |
| `original_rank` | RRF Fusion | $[1, K]$ | Original candidate rank before reranking |
| `rerank_score` | Cross-Encoder | $[0.0, 1.0]$ | Calibrated joint relevance score $P(\text{rel} \mid q, c)$ |
| `rerank_rank` | Cross-Encoder | $[1, K]$ | Final rank position assigned by Cross-Encoder |

Final sorting applies `rerank_score DESC` with deterministic secondary tie-breaking on `(original_rank ASC, chunk_id ASC)`.

---

## 8. Multi-Tenant Isolation

Tenant security is enforced at two distinct boundaries:
1. **Retrieval Boundary**: Dense and Sparse search strictly enforce `organization_id == tenant_context.organization_id`.
2. **Reranking Boundary Guard**: Prior to model inference, `RerankerValidator.validate_tenant_boundaries` asserts that every candidate's `organization_id` strictly matches the authorized `tenant_context.organization_id`. Any mismatch immediately halts execution and raises `RerankerTenantError`.

---

## 9. Post-Rerank Parent Hydration & Zero N+1

Parent chunk hydration is executed **only after** cross-encoder reranking and top-K slicing:
1. Top $K$ reranked candidate IDs (e.g. 10 out of 50) are identified.
2. Parent chunk IDs for those top $K$ chunks are extracted into a unique set.
3. PostgreSQL hydration executes a single batch query via `DocumentChunkRepository.get_by_ids()`:
   ```sql
   SELECT * FROM document_chunks WHERE id IN (:id_1, :id_2, ..., :id_n)
   ```
4. Parent texts are mapped back to reranked chunks in-memory.
5. Candidates ranked outside the top $K$ (e.g. 40 candidates) are never queried from the database, eliminating unnecessary I/O and guaranteeing zero N+1 queries.

---

## 10. Fallback Strategy & Graceful Degradation

If the cross-encoder fails (e.g., timeout, model inference error, CUDA out of memory, uninitialized model):
- If `RERANKER_ALLOW_FALLBACK=True`:
  - Execution gracefully falls back to the original RRF rankings.
  - The response marks `is_degraded = True` and sets `degradation_reason = "CrossEncoder failed: <error details>; fallback to RRF"`.
  - Service availability is maintained without failing user queries.
- If `RERANKER_ALLOW_FALLBACK=False`:
  - `RerankerInferenceError` or `RerankerTimeoutError` is propagated to the API layer for strict monitoring environments.

---

## 11. REST API Integration

The search endpoint `POST /api/v1/retrieval/hybrid-search` is extended with backward-compatible fields:

### Request
```json
{
  "query": "What caused the decline in operating margin?",
  "top_k": 10,
  "rerank": true,
  "rerank_candidates": 50,
  "document_id": null,
  "chunk_type": null,
  "include_parent": true
}
```

### Response
```json
{
  "query": "What caused the decline in operating margin?",
  "retrieval_mode": "hybrid_reranked",
  "total_results": 2,
  "chunks": [
    {
      "chunk_id": "8bc3...-...",
      "document_id": "1fa2...-...",
      "score": 0.985721,
      "rrf_score": 0.016393,
      "rerank_score": 0.985721,
      "rerank_rank": 1,
      "original_rank": 2,
      "dense_score": 0.8124,
      "dense_rank": 2,
      "sparse_score": 1.421,
      "sparse_rank": 2,
      "text": "The severe decline in operating margin was driven by soaring raw material inflation.",
      "parent_text": "Executive Summary..."
    }
  ],
  "diagnostics": {
    "collection_name": "tenant_chunks",
    "dense_candidate_count": 50,
    "sparse_candidate_count": 50,
    "merged_candidate_count": 50,
    "final_result_count": 10,
    "reranking_enabled": true,
    "reranker_provider": "local_deterministic_cross_encoder",
    "reranker_model": "cross-encoder-deterministic-v1",
    "reranker_version": "1.0.0",
    "reranker_candidate_count": 50,
    "is_degraded": false,
    "latency": {
      "dense_ms": 14.2,
      "sparse_ms": 8.1,
      "fusion_ms": 1.2,
      "rerank_ms": 3.4,
      "hydration_ms": 4.1,
      "total_ms": 31.0
    }
  }
}
```

---

## 12. Multilingual Support & Known Limitations

### Support Across Languages
The reranking pipeline supports Arabic, Turkish, English, and mixed multilingual texts without Unicode corruption or normalization faults:
- Arabic: Normalized with diacritic stripping and letter unification via `MultilingualSparseAnalyzer`.
- Turkish: Preserves dotted/dotless `i`/`ı` and case foldings.
- Mixed enterprise queries (e.g. English query matching Arabic financial reports).

### Documented Limitations
1. **Local Provider Semantic Depth**: The `LocalDeterministicCrossEncoderProvider` evaluates lexical alignment, exact phrase matches, and cross-attention window proximity. While deterministic and fast, it lacks deep transformer-based syntactic and contextual reasoning.
2. **Pretrained Neural Models**: HuggingFace models such as `cross-encoder/ms-marco-MiniLM-L-6-v2` were trained primarily on English MS-MARCO datasets. When deployed in production environments requiring high-precision Arabic and Turkish semantic reranking, a multilingual model like `BAAI/bge-reranker-large` or a custom fine-tuned multilingual cross-encoder must be configured in `RERANKER_MODEL`.
3. **Hardware Considerations**: Transformer-based cross-encoders have quadratic computational complexity relative to sequence length. In high-throughput deployments, batch sizes and GPU concurrency limits must be benchmarked under expected tenant query loads.

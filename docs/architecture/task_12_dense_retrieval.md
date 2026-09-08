# Architecture Specification: TASK 12 — Basic Dense Retrieval

## 1. Executive Summary & Core Philosophy

The **Basic Dense Retrieval** subsystem provides enterprise semantic vector search capabilities across parsed and chunked business documents for the **Enterprise AI Analyst** platform. It bridges the embedding model layer ([TASK 10](file:///Users/deneme/Desktop/llmprojesi/docs/architecture/task_10_embeddings.md)) and the Qdrant vector database layer ([TASK 11](file:///Users/deneme/Desktop/llmprojesi/docs/architecture/task_11_vector_store.md)) to translate unstructured natural language queries into ranked, tenant-isolated document chunks.

### Strict Scope Boundaries
To ensure clean modularity and avoid architectural contamination, Task 12 enforces strict operational boundaries:
* **IN-SCOPE**:
  * Query text normalization (NFC) and length/token validation guardrails.
  * Query embedding generation using active Task 10 embedding provider/model configuration.
  * Qdrant dense similarity search using `query_points` with cosine/dot/euclidean metrics.
  * Mandatory tenant isolation (`organization_id`) enforced at both vector filter and result payload verification layers.
  * Metadata filters: `document_id`, `chunk_type`, `page_number`, `section`.
  * Score threshold filtering and strict preservation of raw vector engine distance metrics.
  * Zero N+1 parent and chunk hydration from PostgreSQL.
  * Latency diagnostics and observability breakdown.
  * Standardized REST API: `POST /api/v1/retrieval/search`.
* **STRICTLY OUT-OF-SCOPE (FORBIDDEN IN TASK 12)**:
  * Hybrid retrieval, Sparse retrieval, BM25, and SPLADE.
  * Reciprocal Rank Fusion (RRF) and Score Fusion.
  * Cross-encoders and Cohere/BGE rerankers.
  * Query rewriting, query expansion, and multi-query retrieval.
  * RAG generation, LLM reasoning, agents, citations, and conversational synthesis.

---

## 2. End-to-End Retrieval Flow

```text
Natural Language Query
        ↓
1. QueryValidator (NFC normalize, length checks, token budget checks)
        ↓
2. FilterValidator (top_k bounds, valid ChunkType, positive page_number, tenant check)
        ↓
3. EmbeddingService.embed_query (Provider -> Vector, L2 normalization, embedding cache)
        ↓
4. RetrievalFilterBuilder (Inject mandatory organization_id + optional document/page filters)
        ↓
5. VectorStoreService.search_vectors -> Qdrant (query_points with filter & limit)
        ↓
6. ScoreProcessor (Score threshold filtering, preserve raw distance scores)
        ↓
7. Hydration Phase (Single batch SQL query: WHERE organization_id = :org AND id IN (:chunk_ids))
        ↓
8. Parent Context Hydration (Single batch SQL query: WHERE organization_id = :org AND id IN (:parent_ids))
        ↓
9. Response Assembly & Diagnostics (Format RetrievedChunkResponse & Latency breakdown)
```

---

## 3. Multi-Tenant Isolation & Defense in Depth

Tenant boundaries are strictly preserved across all operations:
1. **API Layer**: `require_tenant_permission(PERM_DOCUMENTS_READ)` extracts and cryptographically validates the caller's JWT claims and `X-Organization-ID` header.
2. **Filter Builder Layer**: `TenantVectorFilterBuilder` mandates `organization_id` in Qdrant's `must` filter clause:
   ```python
   FieldCondition(
       key="organization_id",
       match=MatchValue(value=str(organization_id))
   )
   ```
3. **Payload Defense Layer**: As points are returned from the vector store, every candidate payload is checked:
   ```python
   if payload.get("organization_id") != str(organization_id):
       logger.warning("Tenant isolation triggered: dropped point")
       continue
   ```
4. **Database Hydration Layer**: SQL queries include `WHERE organization_id = :organization_id` ensuring cross-tenant records cannot be fetched even if manipulated point IDs are supplied.

---

## 4. Score Semantics & Preservation

Dense similarity scores represent mathematical distance or similarity in vector space:
* **Cosine Similarity**: Ranges $\in [-1.0, 1.0]$.
* **Dot Product**: Unbounded real numbers $\in (-\infty, \infty)$ (or $[0, 1]$ if normalized).
* **Euclidean (L2) Distance**: Non-negative real numbers $\ge 0.0$.

### Why Artificial Normalization is Prohibited
Mapping non-cosine metrics artificially into a $[0.0, 1.0]$ range introduces mathematical distortions and destroys distance proportionality. Task 12 strictly preserves the raw score returned by Qdrant. Threshold checks evaluate whether `score >= score_threshold`.

---

## 5. Hydration & Zero N+1 Queries Guarantee

When vector search returns $K$ matches, retrieving full chunk text and metadata must not execute $K$ separate SQL queries.

### Implementation
1. **Primary Chunks**: `DocumentChunkRepository.get_by_ids(session, ids, organization_id)` executes:
   ```sql
   SELECT * FROM document_chunks
   WHERE organization_id = :org_id AND id IN (:id_1, :id_2, ..., :id_K);
   ```
2. **Parent Chunks**: If `include_parent=True`, distinct non-null `parent_chunk_id`s are collected and fetched in a second batch query:
   ```sql
   SELECT * FROM document_chunks
   WHERE organization_id = :org_id AND id IN (:parent_id_1, ..., :parent_id_M);
   ```
3. **Result**: For any $K$ (e.g. 50 chunks), exactly **1 or 2 queries** are executed, guaranteeing **0 N+1 queries**.

---

## 6. API Reference

### `POST /api/v1/retrieval/search`

#### Request Payload (`DenseRetrievalRequest`)
```json
{
  "query": "What were the Q3 operating revenues?",
  "top_k": 5,
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "chunk_type": "text",
  "page_number": 1,
  "section": "Financial Highlights",
  "score_threshold": 0.5,
  "include_parent": true
}
```

#### Response Container (`DenseRetrievalResponse`)
```json
{
  "query": "What were the Q3 operating revenues?",
  "total_results": 1,
  "results": [
    {
      "chunk_id": "a5e43b6e-58d0-406b-b4a6-a3ecbb181e1e",
      "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "score": 0.8924,
      "text": "Q3 Enterprise revenue grew by 25% year over year reaching record margins.",
      "chunk_index": 1,
      "chunk_type": "text",
      "token_count": 14,
      "character_count": 73,
      "page_number": 1,
      "page_end": 1,
      "section": "Financial Highlights",
      "heading_hierarchy": ["Executive Summary", "Financial Highlights"],
      "parent_chunk_id": "7b89fd67-3b60-4b69-81a3-b7abb225acbd",
      "parent_text": "Executive Summary: Comprehensive review of Q3 performance.",
      "metadata": {}
    }
  ],
  "diagnostics": {
    "collection_name": "enterprise_ai__local__text_embedding_3_small__1536__1_0_0",
    "embedding_provider": "local",
    "embedding_model": "text-embedding-3-small",
    "dimensions": 1536,
    "query_character_count": 38,
    "query_token_count": 7,
    "total_candidates_found": 1,
    "returned_chunks_count": 1,
    "score_threshold": 0.5,
    "latency": {
      "embedding_ms": 1.25,
      "vector_search_ms": 3.82,
      "hydration_ms": 1.95,
      "total_ms": 7.02
    }
  }
}
```

---

## 7. Diagnostics & Latency Breakdown

Every retrieval execution returns granular latency metrics:
* `embedding_ms`: Time taken by the tokenizer and embedding provider to generate the query vector.
* `vector_search_ms`: Round-trip execution time against Qdrant (`query_points`).
* `hydration_ms`: Time spent querying PostgreSQL for chunk and parent content.
* `total_ms`: End-to-end service execution time.

---

## 8. Transition to Task 13 (Hybrid Retrieval)

The `DenseRetrievalService` developed here acts as the dense foundation for future tasks:
* **TASK 13**: Will introduce BM25 / Sparse retrieval and combine results with this dense retriever using Reciprocal Rank Fusion (RRF).
* **TASK 14**: Will add Cross-Encoder Reranking on top of fused results.
* **TASK 15**: Will implement Query Rewriting & Multi-Query decomposition.

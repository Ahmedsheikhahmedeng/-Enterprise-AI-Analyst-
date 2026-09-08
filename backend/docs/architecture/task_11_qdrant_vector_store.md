# TASK 11 — Qdrant Vector Store & Dense Vector Indexing Architecture

## 1. Executive Summary

Task 11 establishes an enterprise-grade vector database layer utilizing **Qdrant** for the *Enterprise AI Analyst* platform. It connects the intelligent chunking pipeline (`DocumentChunk` from Task 9) and dense embeddings (`DocumentChunkEmbedding` from Task 10) to a resilient, versioned, multi-tenant vector store.

The vector store layer strictly stops at vector lifecycle management:
```text
DocumentChunk
      ↓
Embedding Generation (Task 10)
      ↓
Qdrant Vector Store (Task 11)
      ↓
Upsert / Delete / Inspect
```

### Strict Scope Boundary
- **Dense Vector Upsert & Indexing**: IMPLEMENTED
- **Collection Lifecycle & Schema Management**: IMPLEMENTED
- **Multi-Tenant Filter Enforcement**: IMPLEMENTED
- **Deterministic Point ID Generation**: IMPLEMENTED
- **Payload Schema & Security Validation**: IMPLEMENTED
- **Document & Chunk Vector Deletion**: IMPLEMENTED
- **Health Checks & Observability Stats**: IMPLEMENTED
- **Retrieval API**: NOT IMPLEMENTED
- **Semantic Search**: NOT IMPLEMENTED
- **Hybrid Retrieval**: NOT IMPLEMENTED
- **Sparse Vectors**: NOT IMPLEMENTED
- **Reciprocal Rank Fusion (RRF)**: NOT IMPLEMENTED
- **Cross-Encoder / Reranking**: NOT IMPLEMENTED
- **Query Rewriting**: NOT IMPLEMENTED
- **RAG & LLM Agents**: NOT IMPLEMENTED

---

## 2. Architectural Design & Abstraction Layer

Application services are strictly decoupled from the Qdrant SDK via the `VectorStore` Protocol:

```text
Application Service (DocumentVectorIndexingService)
        ↓
VectorStore Interface Protocol (app.vectorstore.providers.base.VectorStore)
        ↓
Qdrant Provider Implementation (app.vectorstore.providers.qdrant.QdrantVectorStoreProvider)
        ↓
Qdrant Engine (AsyncQdrantClient - HTTP/gRPC or In-Memory Rust Engine)
```

### Directory Structure
```text
app/vectorstore/
├── __init__.py                # Public symbols export
├── collection.py              # CollectionManager, naming sanitization, payload indexes
├── config.py                  # VectorStoreConfig dataclass
├── exceptions.py              # VectorStore exception hierarchy
├── filters.py                 # TenantVectorFilterBuilder
├── hashing.py                 # compute_vector_point_id (UUIDv5)
├── health.py                  # VectorStoreHealthChecker
├── models.py                  # VectorPoint, VectorStoreStats, IndexingBatchResult
├── payload.py                 # PayloadBuilder, secret scanner
├── schemas.py                 # Pydantic DTOs for APIs
├── service.py                 # Domain VectorStoreService orchestrator
└── providers/
    ├── __init__.py
    ├── base.py                # VectorStore Protocol
    ├── fake.py                # FakeVectorStoreProvider (for unit tests)
    └── qdrant.py              # QdrantVectorStoreProvider (with retry & concurrency)
```

---

## 3. Collection Strategy

To guarantee absolute mathematical and model safety, vectors produced by different models, dimensions, distance metrics, or model versions are never mixed in the same physical collection.

### Deterministic Collection Naming
```text
{prefix}__{provider}__{model}__{dimensions}__{version}
```

Example:
```text
enterprise_ai__openai__text_embedding_3_small__1536__1_0_0
```

All tokens are sanitized to lowercase alphanumeric strings with underscores replacing invalid characters.

### Multi-Tenant Strategy
Within a single versioned collection, multiple tenant organizations share the collection safely using **mandatory tenant payload filtering**:
- Every vector point contains `organization_id` in its payload.
- Every read, delete, and count operation is programmatically bound by `TenantVectorFilterBuilder`.
- Unscoped vector store operations are structurally prohibited at the provider layer.

---

## 4. Point ID Generation Strategy

Qdrant point IDs are required to be either 64-bit unsigned integers or standard UUID strings. To ensure strict idempotency and eliminate duplicate vectors upon repeated indexing:

Point IDs are computed as **deterministic UUIDv5** using a dedicated DNS namespace:
```python
UUIDv5(NAMESPACE_DNS, f"urn:vectorpoint:{organization_id}:{chunk_id}:{embedding_input_hash}")
```

### Guarantees
1. Same chunk + same tenant + same embedding content = **Identical UUIDv5 point ID**.
2. Different tenant = **Different point ID** (preventing cross-tenant collision).
3. Modified chunk text = **Different point ID** (safely creating new vector without corrupting prior state).
4. Calling upsert multiple times performs an update in-place without increasing total vector counts.

---

## 5. Payload Schema & Defense Against Secret Leakage

Each vector point contains rich metadata for downstream filtering, citation reconstruction, and observability.

### Payload Fields
| Field | Type | Description |
|---|---|---|
| `organization_id` | `str (UUID)` | Mandatory tenant identifier for isolation |
| `document_id` | `str (UUID)` | Parent document identifier |
| `chunk_id` | `str (UUID)` | Primary key of the chunk |
| `parent_chunk_id` | `str (UUID) \| None` | Parent chunk ID for hierarchical chunking |
| `chunk_index` | `int` | Sequential chunk index within the document |
| `chunk_type` | `str` | Type of chunk (`text`, `table`, `heading`, etc.) |
| `page_number` | `int \| None` | Source document page number |
| `heading_path` | `list[str]` | Heading hierarchy path |
| `heading_context` | `str` | Formatted breadcrumb path |
| `section` | `str \| None` | Section name |
| `content_hash` | `str` | Hash of the raw chunk content |
| `embedding_input_hash`| `str` | Hash of text passed to embedding model |
| `embedding_provider` | `str` | Provider (`openai`, `cohere`, `local`) |
| `embedding_model` | `str` | Model identifier |
| `embedding_version` | `str` | Embedding pipeline version |
| `embedding_dimensions` | `int` | Vector dimension size |
| `normalization` | `str` | Normalization type (`l2`, `none`) |
| `token_count` | `int` | Token count |
| `character_count` | `int` | Character count |
| `chunker_version` | `str` | Chunker version |
| `content` | `str` | Compact chunk text content for retrieval |
| `indexed_at` | `str (ISO8601)` | Indexing timestamp |

### Payload Security & Secret Prevention
- All payloads pass through `PayloadBuilder.validate_payload_security()`.
- Forbidden credential patterns (`api_key`, `access_token`, `refresh_token`, `password`, `secret`, `bearer`, `private_key`) trigger an immediate `VectorStoreValidationError`.
- Document content is treated as untrusted text; no instructions within chunk text are parsed or executed.

---

## 6. Vector Store Configuration & Lifecycle

Centralized configuration in `app/core/config.py`:
- `QDRANT_URL`: `http://localhost:6333`
- `QDRANT_API_KEY`: Optional auth token
- `QDRANT_TIMEOUT_SECONDS`: Request timeout (default: 30.0s)
- `QDRANT_COLLECTION_PREFIX`: Base collection prefix (default: `enterprise_ai`)
- `QDRANT_DISTANCE`: Metric distance (`cosine`, `dot`, `euclidean`)
- `QDRANT_VECTOR_SIZE`: Optional fallback dimension size
- `QDRANT_UPSERT_BATCH_SIZE`: Batch size for ingestion (default: 100)
- `QDRANT_MAX_CONCURRENT_REQUESTS`: Backpressure concurrency semaphore (default: 5)
- `QDRANT_RETRY_COUNT`: Maximum retries on transient network errors (default: 3)
- `QDRANT_RETRY_BACKOFF`: Initial exponential backoff delay (default: 0.5s)

### Client Lifecycle
- `app.state.qdrant_client` is initialized once during FastAPI lifespan startup.
- Provider and domain services are constructed on `app.state` and reused across requests.
- Upon application shutdown, client sessions are cleanly closed.

---

## 7. Payload Indexes

During collection creation (`CollectionManager.ensure_collection()`), mandatory payload indexes are provisioned idempotently:
1. `organization_id` (`KEYWORD`): Required for tenant filtering.
2. `document_id` (`KEYWORD`): Required for document deletion and document-scoped filtering.
3. `chunk_id` (`KEYWORD`): Required for chunk-scoped lookups and single chunk deletion.
4. `chunk_type` (`KEYWORD`): Enables filtering by text, table, or code blocks.
5. `page_number` (`INTEGER`): Enables range filtering across document pages.
6. `embedding_version` (`KEYWORD`): Enables filtering by embedding generation version.

---

## 8. Batch Upsert, Concurrency & Retry Policies

### Micro-Batching
Incoming chunks are processed in chunks bounded by `QDRANT_UPSERT_BATCH_SIZE` (default: 100 points).

### Concurrency Backpressure
Requests are throttled using an `asyncio.Semaphore(config.max_concurrent_requests)` to protect both the application event loop and the Qdrant cluster from exhaustion.

### Retry Strategy
- **Transient Failures Retried**: Network timeouts, connection resets, 502/503/504 errors. Retried with exponential jittered backoff ($0.5s, 1.0s, 2.0s$).
- **Permanent Failures NOT Retried**: Schema validation errors, vector dimension mismatches, NaN/Inf values, tenant isolation violations, authentication errors. These fail fast.

---

## 9. Consistency Model & Failure Recovery

### Dual-Database Consistency
PostgreSQL and Qdrant participate in separate persistence layers without distributed 2PC transactions. The pipeline enforces an ordered state progression:

```text
1. Embeddings Persisted in PostgreSQL (status = "pending")
             ↓
2. Document Status Transitioned to "indexing"
             ↓
3. Vectors Upserted to Qdrant Collection
             ↓
4. Chunk Embeddings Updated (indexing_status = "indexed", point_id, indexed_at)
             ↓
5. Document Status Transitioned to "indexed"
```

### Failure Handling
- **Qdrant Upsert Failure**: The document is marked `failed` with the error reason. PostgreSQL embeddings retain `pending` status. A retry can be triggered at any time via `POST /api/v1/documents/{id}/index`. Because Point IDs are deterministic, retries update in-place with zero duplication risk.
- **Cascaded Soft Delete**: Soft-deleting a document via `DELETE /api/v1/documents/{id}` automatically triggers `delete_document_vectors`, purging all associated points from Qdrant under strict tenant isolation.

---

## 10. Observability & Health

### Health Probe
- `GET /api/v1/vectorstore/health`: Returns connectivity status, latency in milliseconds, and active collections.

### Collection Observability
- `GET /api/v1/vectorstore/collections/{collection_name}`: Returns total points, indexed vectors, vector dimensions, distance metric, and cluster status.

### Document Indexing Status
- `GET /api/v1/documents/{id}/index-status`: Reports total chunks, indexed chunks, pending chunks, and indexing status (`vector_pending`, `vector_indexing`, `vector_indexed`).

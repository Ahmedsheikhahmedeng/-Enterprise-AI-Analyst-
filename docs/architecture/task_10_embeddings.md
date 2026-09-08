# Task 10 — Embeddings & Embedding Provider Abstraction

## 1. Architectural Overview

The **Embeddings & Embedding Provider Abstraction** subsystem transforms semantic `DocumentChunk` records (produced in Task 9) into dense numeric vector representations for downstream indexing in Qdrant (Task 11) and hybrid retrieval/RAG (subsequent tasks).

```text
DocumentChunk
      │
      ▼
DocumentEmbeddingPipelineService (Tenant-isolated orchestration)
      │
      ▼
EmbeddingService (Domain orchestrator)
      │
      ├── EmbeddingTextBuilder (Heading context + content without mutating chunk)
      ├── UniversalEmbeddingTokenizer (Multilingual BPE / token validation)
      ├── EmbeddingCache (Redis / In-Memory / No-op)
      ├── ChunkBatcher (Partitioning & AsyncIO Semaphore concurrency backpressure)
      │
      ▼
EmbeddingProvider (Unified protocol abstraction)
      ├── LocalDeterministicEmbeddingProvider (Deterministic unit vectors, offline)
      ├── OpenAIEmbeddingProvider (HTTP-based decoupled httpx client with backoff)
      └── Custom / Future Providers (Ollama, Azure, vLLM)
      │
      ▼
Validators & Normalization (L2 norm, finite floats, exact dimension invariants)
      │
      ▼
Persistence: document_chunk_embeddings (PostgreSQL metadata only; vectors reserved for Qdrant)
```

---

## 2. Separation of Concerns & Scope Boundaries

* **No Qdrant Indexing**: Collections, payload schemas, and point upserts are strictly excluded (deferred to Task 11).
* **No Retrieval / Search**: Vector search, similarity search, dense/sparse hybrid search, and RRF are excluded.
* **No RAG / Generation**: No LLM generation, prompt templates, or agentic query rewriting.
* **No Vector Storage in PostgreSQL**: Dense float arrays are not stored in PostgreSQL tables; PostgreSQL only holds deterministic hashes, status, token counts, and model metadata.

---

## 3. Provider Abstraction Protocol

The provider layer is completely decoupled from application business logic and external vendor SDKs (`from openai import ...` is strictly forbidden in core services):

```python
@runtime_checkable
class EmbeddingProvider(Protocol):
    @property
    def provider_name(self) -> str: ...
    @property
    def model_name(self) -> str: ...
    @property
    def dimensions(self) -> int: ...

    async def embed_texts(self, texts: Sequence[str]) -> ProviderEmbeddingResponse: ...
    async def health_check(self) -> bool: ...
```

### Implementations

1. **`LocalDeterministicEmbeddingProvider`**:
   - Generates deterministic pseudo-random unit vectors using seeded SHA-256 slices.
   - Guaranteed offline execution, zero network flakiness, perfect for test suites and air-gapped deployments.
2. **`OpenAIEmbeddingProvider`**:
   - Uses `httpx.AsyncClient` directly to send REST POST requests to `/embeddings`.
   - Supports `text-embedding-3-small`, `text-embedding-3-large`, and custom base URLs (vLLM, Ollama, Azure OpenAI).
   - Enforces strict index-based ordering, non-retryable 4xx handling, and exponential backoff on 429/5xx.
3. **`EmbeddingProviderFactory`**:
   - Constructs and configures provider instances from domain settings.
   - Raises `EmbeddingConfigurationError` for unsupported providers without leaking secrets.

---

## 4. Input Preparation & Content Immutability

The `EmbeddingTextBuilder` prepares semantic representations by prepending the heading hierarchy:

```text
Financial Performance > Revenue

Revenue increased by 24% year-over-year to $120 million in Q4 2025.
```

### Strict Guarantees:
- **Source Immutability**: `DocumentChunk.content` is never mutated or overwritten.
- **No Technical Noise**: Database primary keys, tenant UUIDs, trace IDs, and hash strings are excluded from the embedding text.

---

## 5. Multilingual Normalization & Quality

The normalization layer preserves language nuances across Arabic, Turkish, English, and mixed documents:
- **Unicode NFKC Normalization**: Ensures canonical equivalence without corrupting Arabic diacritics/characters (e.g. `تحليل أداء الشركة`) or Turkish dotted/dotless letters (`ı, İ, ç, ş, ğ, ö, ü`).
- **Whitespace Collapsing**: Collapses redundant horizontal spaces while preserving logical paragraph breaks.
- **Empty Chunk Validation**: Empty or whitespace-only chunks are rejected prior to sending API requests.

---

## 6. Token Limits & Safety

- Token limits are evaluated via `UniversalEmbeddingTokenizer`.
- Evaluates token count against `EMBEDDING_MAX_INPUT_TOKENS`.
- **No Silent Truncation**: If a chunk exceeds the maximum token limit, the service raises `EmbeddingInvalidInputError` rather than silently cutting text and losing critical semantic context.

---

## 7. Batching, Concurrency, and Order Preservation

1. **Batching**: Chunks are partitioned into batches of size `EMBEDDING_BATCH_SIZE` (default: 64).
2. **Backpressure**: Batch execution is throttled via `asyncio.Semaphore(max_concurrency=MAX_CONCURRENT_REQUESTS)` (default: 5 concurrent workers) to prevent rate limits and socket exhaustion.
3. **Strict Ordering**: Batch tasks are reassembled and sorted by original index to ensure that vector $i$ corresponds strictly to chunk $i$.

---

## 8. Vector Validation & L2 Normalization

Every vector returned by an embedding provider must satisfy:
1. **Dimension Match**: `len(vector) == EMBEDDING_DIMENSIONS`. Mismatches raise `EmbeddingDimensionError`.
2. **Finite Reals**: Every float must satisfy `math.isfinite(x)`. Any `NaN`, `+Inf`, or `-Inf` raises `EmbeddingValidationError`.
3. **Configurable L2 Normalization**: If `EMBEDDING_NORMALIZE = True`, vectors are normalized via $v / \|v\|_2$ with $\epsilon = 10^{-12}$ to safeguard against zero division.

---

## 9. Deterministic Identity & Caching Layer

### Identity Hash
Each embedding is identified by a SHA-256 fingerprint:
$$\text{hash} = \text{SHA-256}(\text{normalized\_text} \parallel \text{provider} \parallel \text{model} \parallel \text{version} \parallel \text{dimensions} \parallel \text{norm})$$

### Cache Abstraction
- Protocol: `EmbeddingCache` with `get`, `set`, `get_many`, and `set_many`.
- Implementations: `RedisEmbeddingCache`, `InMemoryEmbeddingCache`, `NoopEmbeddingCache`.
- **Key Safety**: Namespaced keys: `embedding:{provider}:{model}:{version}:{input_hash}`. Raw document content is never included in cache keys.

---

## 10. Cost & Observability Metadata

Every batch tracks observability metrics:
- Provider, model, version, dimensions, batch size, input count, total tokens, latency (ms), retry count, cache hits, cache misses, and estimated cost calculated via `EmbeddingPricing`.
- Raw text chunks are omitted from logging to respect tenant confidentiality.

---

## 11. Database Persistence & Migration

### Schema: `document_chunk_embeddings`
Option B was chosen to preserve separation between PostgreSQL relational metadata and future Qdrant vector storage:

```sql
CREATE TABLE document_chunk_embeddings (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    dimensions INTEGER NOT NULL,
    normalization VARCHAR(50) NOT NULL,
    embedding_input_hash VARCHAR(64) NOT NULL,
    token_count INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Indexes are created for tenant scoping (`organization_id`), document queries, chunk links, status, and input hashes.

---

## 12. Re-Embedding & Idempotency

- Repeated invocations with identical configuration and chunks check the cache and database, returning the completed summary without duplicated provider calls.
- Calling with `force=True` cleanly purges existing embedding records for that document and regenerates new embeddings.
- When model, dimensions, or version change, hashes change, allowing re-embedding detection.

---

## 13. Security, RBAC & Multi-Tenancy

- **Tenant Isolation**: Every database operation and API endpoint enforces `organization_id` matching from `TenantContext`. Cross-tenant queries return 404.
- **RBAC**: Generating embeddings requires `documents.write` (Admin, Analyst). Viewing embeddings requires `documents.read` (Viewer).
- **Secret Protection**: API keys are injected via environment variables (`EMBEDDING_API_KEY`) and never logged or serialized in error messages.

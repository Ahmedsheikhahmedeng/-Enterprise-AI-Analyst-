# Task 9 — Intelligent / Semantic Chunking Architecture

## 1. Overview & Objective

Task 9 implements the enterprise chunking layer for the **Enterprise AI Analyst** platform. It transforms canonical normalized parsed documents (`ParsedDocument`, produced by Task 8) into high-quality, structure-aware, deterministic, and multilingual **Document Chunks** (`DocumentChunk`) stored in PostgreSQL.

These chunks form the foundational retrieval units for downstream vector indexing (Task 10), hybrid search, and RAG operations.

```text
ParsedDocument (Task 8 Ingestion)
      │
      ▼
ChunkingService (app/chunking/service.py)
      │
      ├─► Structure & Heading Analysis (boundaries.py: HeadingPathTracker)
      ├─► Boundary Detection & Splitting (boundaries.py: SentenceSplitter)
      ├─► Chunking Strategies (strategies.py)
      │       ├── TableChunkingStrategy (Headers replicated across all slices)
      │       ├── ListChunkingStrategy (Item cohesion preserved)
      │       └── HugeBlockFallbackStrategy (Paragraph -> Sentences -> Token window fallback)
      ├─► Small Fragment Merging (Orphan headings combined with following content)
      ├─► Conservative Deduplication (Content hash + context + page matching)
      ├─► Parent / Child Hierarchy Generation (parent_child.py)
      │       ├── Parent: Broad context container (Section level, <= MAX_PARENT_TOKENS)
      │       └── Child: Granular retrieval unit with parent_chunk_id reference
      ├─► Deterministic Identity & Hashing (hashing.py: UUIDv5 + SHA-256)
      ├─► Quality Validation (validators.py: no empty, no oversized, valid DAG)
      └─► Quality Metrics Computation (metrics.py: ChunkQualitySummary)
      │
      ▼
DocumentChunkRepository (app/repositories/chunk.py: Tenant-isolated bulk persistence)
      │
      ▼
PostgreSQL (`document_chunks` table)
```

---

## 2. Structure-Aware Boundary Strategy

Rather than naive character or fixed-size slicing (`text[:1000]`), the chunking engine respects semantic document boundaries in strict hierarchical order:

1. **Document Level**: Preserves document metadata and ownership.
2. **Page Level**: Preserves physical page numbers (`page_number`) for paginated documents (e.g. PDF).
3. **Section Level**: Preserves logical section boundaries (`ParsedSection`).
4. **Heading Hierarchy**: Tracks nested headings (`HeadingPathTracker`).
5. **Paragraph Level**: Preserves thematic coherence and paragraph breaks (`\n\n`).
6. **List Cohesion**: Keeps list items together.
7. **Table Integrity**: Retains column headers across all table slices.
8. **Sentence Boundaries**: Detects sentence terminators while protecting abbreviations.
9. **Bounded Token Fallback**: Prevents memory exhaustion or out-of-bounds chunks on giant unstructured text blocks.

### Fallback Splitting Sequence
When an element exceeds `MAX_CHUNK_TOKENS`:
```text
Huge Block
    │
    ▼
Split by Paragraphs (\n\n)
    │
    ▼ (if a paragraph is still oversized)
Split into Sentences (SentenceSplitter)
    │
    ▼ (if a single sentence is oversized or continuous)
Windowed Token / Character Segment Fallback (Hard Limit Enforced)
```

---

## 3. Heading Context & Hierarchy

Every generated chunk retains its structural origin in the document's heading tree:
- `heading_path: list[str]`: Hierarchical list of ancestors, e.g. `["Chapter 2: Financials", "Revenue", "International"]`.
- `heading_context: str`: Joined representation, e.g. `"Chapter 2: Financials > Revenue > International"`.

The `HeadingPathTracker` manages a stack of `(level, title)`. When a heading of level $L$ arrives, all headings with level $\ge L$ are popped from the stack, ensuring correct tree navigation even in complex multi-level documents.

---

## 4. Parent / Child Chunk Architecture

To balance precise vector retrieval with broad synthesis context, chunks are structured into a two-tier hierarchy:

```text
Parent Chunk (Section / Topic Cluster, <= 1600 tokens)
    ├── Child Chunk 1 (Paragraph, ~400 tokens, parent_chunk_id = Parent.id)
    ├── Child Chunk 2 (List, ~250 tokens, parent_chunk_id = Parent.id)
    └── Child Chunk 3 (Table Slice, ~350 tokens, parent_chunk_id = Parent.id)
```

- **Child Chunk (`parent_chunk_id != None`)**: Optimized for vector search and precision retrieval.
- **Parent Chunk (`chunk_type = 'parent'`, `parent_chunk_id = None`)**: Preserves the broader conceptual context of the section. When a child chunk is retrieved during search, the downstream LLM generator can fetch its parent chunk to avoid missing context without bloating the child chunk payload.

---

## 5. Specialized Chunking Strategies

### 5.1 Tables (`TableChunkingStrategy`)
- Never treated as unstructured plain text. Rendered as standard Markdown tables.
- **Header Replication**: When a large table is sliced across multiple chunks (due to row counts or token limits), the table headers and separator line (`| --- | --- |`) are **replicated on every single chunk slice**.
- Source locators track `sheet_name`, `row_start`, `row_end`, and `total_rows`.

### 5.2 Lists (`ListChunkingStrategy`)
- Preserves bullet points and numbered lists as contiguous units.
- Splits large lists across item boundaries rather than breaking mid-sentence inside a bullet.

### 5.3 Small Chunk Merging
- Very short fragments (< `SMALL_CHUNK_THRESHOLD_TOKENS`, e.g. orphan headings or short 1-line fragments) are merged with adjacent text in the same section:
  ```text
  [Heading] + [Paragraph] -> [Composite Chunk]
  ```
  This prevents creating isolated 2-token retrieval chunks.

---

## 6. Multilingual Support & Token Counter Abstraction

The chunking subsystem includes a vendor-neutral token counting abstraction:
- Interface: `TokenCounter(ABC)` with `count_tokens`, `split_into_tokens`, and `truncate_to_tokens`.
- Implementation: `MultilingualTokenCounter`.
- Language support:
  - **Arabic**: Accurate word tokenization preserving Arabic script, hamzas, and diacritics / tashkeel (`\u064B-\u065F`).
  - **Turkish**: Handles agglutinative roots and accented letters (`ç, ğ, ı, ö, ş, ü, İ`).
  - **English**: Word clusters, standard decimal numbers, and abbreviations.
  - Subword approximation: Tokens longer than 8 characters are scaled by $\sim 1.3\times$ to align closely with standard BPE tokenizers.

---

## 7. Determinism, Content Hashing, and Idempotency

### Deterministic Chunk Identity
Chunk IDs are calculated using UUIDv5:
```python
seed = f"{document_id}:{chunk_index}:{chunker_version}:{content_hash}"
chunk_id = uuid.uuid5(uuid.NAMESPACE_DNS, seed)
```
Re-running chunking on an identical document with identical parser and chunker versions produces **100% identical chunk IDs**.

### Content Hashing
Normalized SHA-256 hex digest:
```python
content_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
```
Normalization applies Unicode NFKC and collapses consecutive whitespace.

### Idempotent Reprocessing
When a document is re-chunked:
1. Active chunks for `(organization_id, document_id)` are deleted transactionally via `DocumentChunkRepository.delete_by_document(...)`.
2. New intermediate chunks are bulk inserted within the same database transaction.
3. If chunking fails, the transaction rolls back, preventing partial or duplicated chunk states.

---

## 8. Database Schema & Migration

Alembic migration `b2c272705698_add_document_chunk_semantic_fields` enhanced the `document_chunks` table with:

| Column | Type | Constraints / Indexes | Purpose |
| :--- | :--- | :--- | :--- |
| `parent_chunk_id` | UUID | FK to `document_chunks.id` (ON DELETE CASCADE), Indexed | Parent/child link |
| `heading_context` | TEXT | Nullable | Formatted heading breadcrumb |
| `heading_path` | JSONB | Nullable | Ancestor headings array |
| `source_locator` | JSONB | Nullable | Document, page, section, row indices |
| `token_count` | INTEGER | Default 0, Not Null | Estimated token count |
| `character_count` | INTEGER | Default 0, Not Null | Exact character length |
| `content_hash` | VARCHAR(64) | Indexed with `organization_id` | SHA-256 normalized hash |
| `chunker_version` | VARCHAR(50) | Default "1.0.0", Not Null | Chunker version tag |

---

## 9. Quality Validation & Metrics

### Quality Rules Enforced (`validate_chunks`)
- No empty or whitespace-only chunks.
- No chunks exceeding hard limits (`MAX_CHUNK_TOKENS=800`, `MAX_CHUNK_CHARACTERS=4000`, `MAX_PARENT_TOKENS=1600`).
- Exact character count match (`character_count == len(content)`).
- Sequential non-negative `chunk_index`.
- Valid parent references: every child points to a valid chunk of type `parent` in the current document.
- Cycle prevention: `parent_chunk_id != chunk.id`.
- Tenant and document ownership invariant.

### Quality Metrics Summary (`ChunkQualitySummary`)
Produced after every chunking run and accessible via `GET /api/v1/documents/{id}/chunks/summary`:
- `total_chunks`, `parent_chunks`, `child_chunks`
- Breakdown by type: `text_chunks`, `table_chunks`, `list_chunks`, `composite_chunks`
- Distribution: `min_tokens`, `max_tokens`, `mean_tokens`, `median_tokens`
- Integrity: `oversized_chunks`, `empty_chunks`, `duplicate_ratio`
- Coverage: `pages_covered: list[int]`, `sections_covered: list[str]`

---

## 10. API Endpoints & RBAC

| Method | Endpoint | Permission | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/documents/{id}/chunks` | `documents.write` | Trigger chunking or reprocess (`sync=true` or async worker) |
| `GET` | `/api/v1/documents/{id}/chunks` | `documents.read` | List chunks (supports `skip`, `limit`, `parent_only=true`) |
| `GET` | `/api/v1/documents/{id}/chunks/summary` | `documents.read` | Retrieve chunk quality and distribution metrics |

---

## 11. Known Limitations & Future Work

- **LLM/Agent Boundaries**: No semantic clustering using LLMs or embedding models is performed in Task 9 (strictly scoped to Task 10+).
- **OCR Slicing**: For scanned PDFs without bounding box coordinates, visual layout column reordering relies on text extraction order from Task 8 parsers.

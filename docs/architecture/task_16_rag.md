# TASK 16 — Evidence-Grounded RAG & Answer Generation Architecture

## Overview

The **Evidence-Grounded RAG & Answer Generation** subsystem forms the factual analytical synthesis layer of the *Enterprise AI Analyst* platform. Positioned directly downstream of Query Understanding ([TASK 15](file:///Users/deneme/Desktop/llmprojesi/docs/architecture/task_15_query_understanding.md)), Multi-Query Hybrid Retrieval ([TASK 13](file:///Users/deneme/Desktop/llmprojesi/docs/architecture/task_13_hybrid_retrieval.md)), and Cross-Encoder Reranking ([TASK 14](file:///Users/deneme/Desktop/llmprojesi/docs/architecture/task_14_reranking.md)), it synthesizes verified document excerpts into structured, factual answers backed by citation references while strictly preventing hallucinations, prompt injections, and cross-tenant leakage.

```text
User Query (AR / TR / EN / Mixed)
     ↓
Query Understanding & Planning (Task 15)
     ↓
Multi-Query Hybrid Retrieval & RRF Fusion (Task 13/15)
     ↓
Cross-Encoder Reranking & Top-K Pool (Task 14)
     ↓
Post-Rerank Parent Chunk Hydration (Zero N+1)
     ↓
Evidence Selection & Tenant Isolation Gate
     ↓
Light Diversity & Deduplication
     ↓
Context Assembly & Token Packing (Max 4,000 Tokens)
     ↓
Prompt Construction with Injection Boundaries (<evidence>)
     ↓
LLM Answer Generation (Deterministic Local Provider / OpenAI)
     ↓
Grounding & Citation Validation (Phantom Citation Repair)
     ↓
Confidence Calculation & Contradiction Detection
     ↓
Persistence (AnalysisStep, LLMRequest, UsageEvent)
     ↓
Structured Grounded Answer + Citations + Telemetry
```

---

## 1. Core Architecture & Component Responsibilities

### 1.1 `RAGService` Orchestrator ([app/rag/service.py](file:///Users/deneme/Desktop/llmprojesi/backend/app/rag/service.py))
Coordinates end-to-end flow without embedding vendor-specific SDKs, SQL queries, or vector store calls:
1. **Query Planning**: Invokes `QueryUnderstandingService` to produce a structured `SearchPlan`.
2. **Retrieval**: Executes candidate retrieval through `HybridRetrievalService.search()`.
3. **Fast Exit**: If retrieval returns zero chunks or all candidates fall below `min_evidence_score`, immediately returns an ungrounded response ("لم أجد معلومات كافية في المستندات المتاحة") with 0 ms LLM latency, avoiding hallucinated answers and unnecessary generation costs.
4. **Evidence Selection**: Filters, deduplicates, and validates tenant boundaries via `EvidenceSelector`.
5. **Context Assembly**: Packs highest reranked evidence items up to `RAG_MAX_CONTEXT_TOKENS` via `ContextAssembler`.
6. **Prompt Building**: Enforces system anti-hallucination rules and wraps evidence in `<evidence>` tags via `PromptBuilder`.
7. **Generation**: Invokes `RAGLLMProvider` with temperature 0.0 and structured JSON schema requirements.
8. **Grounding Validation**: Validates citations, strips phantom references, checks for contradictions, and computes composite confidence via `GroundingValidator`.
9. **Persistence**: Records execution telemetry into `AnalysisStep`, `LLMRequest`, and `UsageEvent` when a database session is provided.

---

## 2. Evidence Model & Selection

### 2.1 Domain Model ([app/rag/models.py](file:///Users/deneme/Desktop/llmprojesi/backend/app/rag/models.py))
Each evidence block is encapsulated in an immutable dataclass:
- `evidence_id`: Sequential tag (`E1`, `E2`, ...) used for LLM citations.
- `chunk_id`: Unique UUID of the specific text chunk.
- `document_id`: UUID of the parent document.
- `organization_id`: Tenant identifier guaranteeing data isolation.
- `rank`: Ordinal position in candidate pool after cross-encoder reranking.
- `rerank_score`: Relevance score from cross-encoder model.
- `text`: Chunk text or hydrated parent context.
- `page_number`: Document page number.
- `heading_path`: Hierarchical section trail (e.g. `Financials > Operating Expenses`).
- `source_locator`: Human-readable locator string (`Document: 10K.pdf, Page: 8, Section: Operating Expenses`).
- `document_name`: Name or filename of the source document.

### 2.2 Tenant Boundary Enforcement
In `EvidenceSelector.select_evidence`:
```python
for chunk in chunks:
    if chunk.organization_id != organization_id:
        raise RAGTenantMismatchError("Cross-tenant candidate detected")
```
Every candidate is strictly validated against the calling tenant before entering context assembly. Any mismatch aborts execution immediately.

### 2.3 Deduplication & Light Diversity
- **Deduplication**: Chunks sharing the same `chunk_id` across multi-query formulations are deduplicated, keeping the highest-ranked entry.
- **Light Diversity**: Prevents a single document from dominating all top-K context slots (configurable `max_per_document=3`), ensuring broader topical coverage when multiple relevant documents exist.

---

## 3. Context Assembly & Token Budgeting

### 3.1 Structured Blocks ([app/rag/context.py](file:///Users/deneme/Desktop/llmprojesi/backend/app/rag/context.py))
Evidence is formatted into distinct contextual blocks:
```text
[Evidence 1] (ID: E1)
Document: Annual_Report_2025.pdf
Section: Financial Summary > Revenues
Page: 8
Content:
In fiscal year 2025 operating revenue expanded to $110 million.
---
[Evidence 2] (ID: E2)
...
```

### 3.2 Token Budget Packing
- Hard ceiling defined by `RAG_MAX_CONTEXT_TOKENS` (default 4,000 tokens).
- Evidence blocks are packed in descending order of rerank relevance.
- Packing stops cleanly before exceeding the budget, preserving complete paragraphs and section headers rather than truncating text mid-sentence.

---

## 4. Prompt Engineering & Injection Defense

### 4.1 System Prompt Template ([app/rag/prompts.py](file:///Users/deneme/Desktop/llmprojesi/backend/app/rag/prompts.py))
- **Versioned**: `RAG_PROMPT_VERSION = "v1"`.
- **Anti-Hallucination**: Requires answering using exclusively facts directly substantiated by supplied evidence.
- **Citation Mandate**: Requires inline citations format `[E1]`, `[E2]`.
- **Contradiction Acknowledgment**: Explicitly directs the model to state conflicting figures if documents diverge, citing both sources without inventing reconciliation.
- **Prompt Injection Defense**: Untrusted user documents are isolated strictly within `<evidence>...</evidence>` XML tags. The system prompt instructs the model that content within evidence tags is raw data and must never be interpreted as commands or system directives.
- **No Chain-of-Thought**: Prohibits internal reasoning exposition, returning only final answer and citations.

---

## 5. Grounding & Citation Validation

### 5.1 Phantom Citation Repair ([app/rag/grounding.py](file:///Users/deneme/Desktop/llmprojesi/backend/app/rag/grounding.py))
If an LLM hallucinates non-existent citations (e.g. citing `[E7]` when only `E1` and `E2` were supplied):
1. `GroundingValidator` detects that `E7` is not in the supplied evidence set.
2. The phantom tag `[E7]` is stripped from the answer text.
3. The invalid ID is removed from `evidence_ids`.
4. A grounding confidence penalty is applied.

### 5.2 Confidence Calculation
Composite grounding confidence blends:
1. **Evidence Quality**: Mean rerank score of verified cited evidence.
2. **Phantom Penalty**: Subtraction for attempted phantom citations.
3. **Model Self-Confidence**: Weighted 60% system grounding score + 40% model claimed confidence.
4. **Ungrounded Cap**: If the answer is ungrounded or indicates lack of data, confidence is capped at $\le 0.3$.

---

## 6. Provider Abstraction

### 6.1 Provider Interface ([app/rag/providers/base.py](file:///Users/deneme/Desktop/llmprojesi/backend/app/rag/providers/base.py))
```python
class RAGLLMProvider(Protocol):
    async def generate(
        self, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float
    ) -> RAGProviderResponse: ...
```

### 6.2 Local Deterministic Provider ([app/rag/providers/local.py](file:///Users/deneme/Desktop/llmprojesi/backend/app/rag/providers/local.py))
- Default provider for automated tests and CI environments (`RAG_LLM_PROVIDER="deterministic"`).
- Produces deterministic, grounded answers quoting the top evidence with accurate `[E1]` citations.
- Reliably detects unsupported topics and conflicting figures.
- Measures token usage and latency without external network calls or costs.

### 6.3 Real HTTP LLM Provider ([app/rag/providers/llm.py](file:///Users/deneme/Desktop/llmprojesi/backend/app/rag/providers/llm.py))
- Direct HTTP interaction with OpenAI or compatible endpoints using `httpx.AsyncClient`.
- Implements exponential backoff retries on transient errors (429, 500, 502, 503, 504).
- Validates output JSON with Pydantic schemas.
- Falls back gracefully to the deterministic provider on failure.

---

## 7. Configuration & Budgets

Configurable via environment variables and application settings:
- `RAG_ENABLED: bool = True`
- `RAG_LLM_PROVIDER: str = "deterministic"` (supports `openai`, `deterministic`)
- `RAG_LLM_MODEL: str = "gpt-4o-mini"`
- `RAG_LLM_TEMPERATURE: float = 0.0`
- `RAG_MAX_OUTPUT_TOKENS: int = 1024`
- `RAG_MAX_CONTEXT_TOKENS: int = 4000`
- `RAG_EVIDENCE_TOP_K: int = 5`
- `RAG_MIN_EVIDENCE_SCORE: float = 0.0`
- `RAG_LLM_TIMEOUT_SECONDS: float = 30.0`
- `RAG_LLM_MAX_RETRIES: int = 2`
- `RAG_PROMPT_VERSION: str = "v1"`
- `RAG_RESPONSE_LANGUAGE: str = "auto"`
- `RAG_MAX_LLM_COST_PER_REQUEST: float = 0.10`

---

## 8. REST API Specification

### `POST /api/v1/rag/answer`
- **Authentication**: JWT Bearer token with `PERM_DOCUMENTS_READ`.
- **Request Body**:
  ```json
  {
    "query": "What was total operating revenue in 2025?",
    "top_k": 5,
    "include_evidence": true
  }
  ```
- **Response Body**:
  ```json
  {
    "answer": "According to the provided documents, In fiscal year 2025 operating revenue expanded to $110 million. [E1]",
    "grounded": true,
    "confidence": 0.94,
    "citations": [
      {
        "evidence_id": "E1",
        "chunk_id": "404313ec-fba0-42bd-82e4-184aca2e54ab",
        "document_id": "2ad0fd22-9725-46d4-abf2-69c9c2335965",
        "page_number": 8,
        "source_locator": "Document: Annual_Report_2025.pdf, Page: 8, Section: Financial Summary > Revenues",
        "document_name": "Annual_Report_2025.pdf"
      }
    ],
    "evidence": [
      {
        "evidence_id": "E1",
        "document_name": "Annual_Report_2025.pdf",
        "page_number": 8,
        "section": "Financial Summary > Revenues",
        "text": "In fiscal year 2025 operating revenue expanded to $110 million.",
        "rerank_score": 0.95
      }
    ],
    "diagnostics": {
      "retrieved": 15,
      "reranked": 15,
      "evidence_used": 1,
      "context_tokens": 42,
      "input_tokens": 62,
      "output_tokens": 24,
      "understanding_ms": 0.45,
      "retrieval_ms": 82.1,
      "rerank_ms": 4.2,
      "llm_latency_ms": 1.2,
      "total_latency_ms": 88.5,
      "model": "deterministic-rag-v1",
      "provider": "deterministic",
      "prompt_version": "v1"
    }
  }
  ```

---

## 9. Scope Boundaries & Non-Goals

| Feature | Status in Task 16 | Future Phase |
| :--- | :--- | :--- |
| **RAG Orchestration** | **IMPLEMENTED** | Core |
| **Evidence Selection & Diversity** | **IMPLEMENTED** | Core |
| **Context Assembly & Token Budgeting** | **IMPLEMENTED** | Core |
| **Grounded Answer Generation** | **IMPLEMENTED** | Core |
| **Citation Verification & Repair** | **IMPLEMENTED** | Core |
| **Tenant Isolation Gate** | **IMPLEMENTED** | Core |
| **Prompt Injection Defense** | **IMPLEMENTED** | Core |
| **Deterministic Local Provider** | **IMPLEMENTED** | Core |
| **SQL Agent / Text-to-SQL** | **EXCLUDED** | Task 17+ |
| **Data Analyst Agent** | **EXCLUDED** | Task 17+ |
| **Tool Calling / Function Calling** | **EXCLUDED** | Task 17+ |
| **Autonomous Multi-Step Agents** | **EXCLUDED** | Task 17+ |
| **Report Generation** | **EXCLUDED** | Future |
| **Autonomous Web Search** | **EXCLUDED** | Future |

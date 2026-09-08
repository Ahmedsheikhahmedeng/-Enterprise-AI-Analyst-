# Enterprise AI Analyst — API Contract & Frontend Compatibility Audit (TASK 44)

## 1. Unified Contract Envelope Architecture
All backend endpoints wrap responses in the canonical `ApiResponse[T]` schema defined in `app/product/contracts.py`:

```json
{
  "data": { ... },
  "error": null,
  "trace_id": "req-1725790000-a1b2c3d"
}
```

When an error occurs, the standard envelope structure is maintained:

```json
{
  "data": null,
  "error": {
    "code": "ENTITY_NOT_FOUND",
    "message": "Dataset not found for current tenant",
    "details": [],
    "retryable": false,
    "request_id": "req-1725790000-a1b2c3d"
  },
  "trace_id": "req-1725790000-a1b2c3d"
}
```

---

## 2. Frontend Typed Client Alignment Audit
The frontend API client (`frontend/lib/api/client.ts`) was audited against the registered OpenAPI schema (289 endpoints across 238 paths):

| Frontend Client Method | Target FastAPI Endpoint | HTTP Method | Schema Match |
|---|---|---|:---:|
| `apiClient.ask.submit` | `/api/v1/ask` | `POST` | **100% MATCH ✅** |
| `apiClient.ask.get` | `/api/v1/ask/{execution_id}` | `GET` | **100% MATCH ✅** |
| `apiClient.ask.cancel` | `/api/v1/ask/{execution_id}/cancel` | `POST` | **100% MATCH ✅** |
| `apiClient.ask.getEvidence` | `/api/v1/ask/{execution_id}/evidence` | `GET` | **100% MATCH ✅** |
| `apiClient.executions.list` | `/api/v1/executions` | `GET` | **100% MATCH ✅** |
| `apiClient.executions.get` | `/api/v1/executions/{id}` | `GET` | **100% MATCH ✅** |
| `apiClient.approvals.listPending` | `/api/v1/approvals/pending` | `GET` | **100% MATCH ✅** |
| `apiClient.approvals.resolve` | `/api/v1/approvals/{id}/resolve` | `POST` | **100% MATCH ✅** |
| `apiClient.datasets.list` | `/api/v1/datasets` | `GET` | **100% MATCH ✅** |
| `apiClient.datasets.get` | `/api/v1/datasets/{id}` | `GET` | **100% MATCH ✅** |
| `apiClient.semantic.getTerms` | `/api/v1/semantic/terms` | `GET` | **100% MATCH ✅** |
| `apiClient.semantic.getMetrics` | `/api/v1/semantic/metrics` | `GET` | **100% MATCH ✅** |
| `apiClient.semantic.getGraph` | `/api/v1/graph/explore` | `GET` | **100% MATCH ✅** |
| `apiClient.evaluation.getScorecards` | `/api/v1/evaluation/scorecards` | `GET` | **100% MATCH ✅** |
| `apiClient.auth.me` | `/api/v1/auth/me` | `GET` | **100% MATCH ✅** |
| `apiClient.auth.login` | `/api/v1/auth/login` | `POST` | **100% MATCH ✅** |
| `apiClient.auth.logout` | `/api/v1/auth/logout` | `POST` | **100% MATCH ✅** |

---

## 3. Server-Sent Events (SSE) Streaming Protocol
The real-time streaming endpoint (`GET /api/v1/ask/{execution_id}/stream`) implements the resilient protocol validated in TASK 34 and TASK 42:
* **Event Sequence Integrity**: Every event transmits `event_id` and monotonic `sequence_number`.
* **Deduplication**: `AnalystSSEClient` drops any duplicate sequence numbers.
* **Stream Replay**: Reconnection includes `after_sequence` parameter to replay missed tokens without data loss.
* **Lifecycle Events**:
  - `CONNECTED`: Session established with active tenant.
  - `STAGE_CHANGED`: Progress update (`UNDERSTANDING` → `SEMANTIC` → `EXECUTION` → `EVIDENCE`).
  - `TOKEN_CHUNK`: Real-time markdown token delta.
  - `CITATION_FOUND`: Real-time provenance pill arrival.
  - `COMPLETED`: Stream finalized with groundedness score.
  - `FAILED` / `CANCELLED`: Terminal failure or graceful user stop.

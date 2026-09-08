# Enterprise AI Analyst — Engineering Portfolio & Architecture Showcase

## 1. Project Overview

The **Enterprise AI Analyst** is a production-grade, multi-tenant intelligence platform that allows enterprises to interact with both unstructured corporate documents and structured transactional databases through grounded natural language queries.

Unlike simple demo RAG or chatbot wrappers, this platform solves hard enterprise engineering challenges:
1. **Hallucination Prevention**: Answers are mathematically grounded with inline citations (`[S1]`, `[S2]`) and verified by an automated hallucination evaluation gate before delivery.
2. **Deterministic SQL Safety**: Text-to-SQL generation operates via semantic modeling with strict read-only AST parsing, tenant row-level security injection, and hard row/time limits.
3. **Enterprise SRE & Reliability**: Multi-burn-rate SLO alerting, automated incident state machines, and chaos-tested failover runbooks.
4. **Internal FinOps Governance**: Real-time token usage accounting, versioned pricing registries, multi-dimensional allocation, and budget hard stops.
5. **Data Sovereignty & Compliance**: Strict data classification rules preventing sensitive (`RESTRICTED`) enterprise data from ever reaching third-party cloud LLMs.

---

## 2. Technology Stack

* **Backend Framework**: Python 3.12, FastAPI, Pydantic V2, Uvicorn.
* **Database & Persistence**: PostgreSQL 16 (Relational schemas, SQLAlchemy 2.0 async, Alembic migrations).
* **Vector & Semantic Search**: Qdrant vector database, Dense (OpenAI `text-embedding-3-small`) + Sparse BM25 tokenizers merged via Reciprocal Rank Fusion (RRF).
* **Distributed Caching & Tasks**: Redis, Celery background workers.
* **Frontend Web Application**: Next.js 16 (App Router + Turbopack), React 19, TypeScript 5, Tailwind CSS, Radix UI.
* **Observability & SRE**: OpenTelemetry tracing, Prometheus metric collectors, multi-window burn rate evaluators.
* **Security**: JWT authentication (HMAC-SHA256), 138-permission RBAC catalog, Row-Level Security, PII sanitization.

---

## 3. Core Engineering Highlights

### Multimodal Evidence Fusion
The platform unifies unstructured document chunks, relational table query results, and knowledge graph relationship paths into a canonical `Evidence` contract. Conflicting data points between corporate filings and relational data are detected and reported to the user with calculated confidence scores.

### Immutable Usage Ledger & Cost Governance
Every single LLM Gateway invocation records an immutable `CostEvent` calculating costs down to sub-cent precision (`Decimal(12, 4)`). Budgets enforce preflight validation, blocking requests before provider dispatch when hard limits are reached.

### Deterministic State Machine Enforcement
All long-running entities—Agents, Background Jobs, SRE Incidents, Human Approvals, and FinOps Budgets—are governed by finite state machines with zero unreachable or orphaned terminal states.

---

## 4. Verification & Production Readiness

* **1,097 Automated Unit & Integration Tests** passing at 100%.
* **26 End-to-End User Journey Tests** covering all canonical workflows.
* **Zero Database Schema Drift** (`alembic check` clean).
* **Zero Linter or Type Errors** across both Python backend (`mypy`, `ruff`) and Next.js frontend (`tsc --noEmit`, `eslint`).

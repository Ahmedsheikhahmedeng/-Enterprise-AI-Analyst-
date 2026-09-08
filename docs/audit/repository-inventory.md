# Enterprise AI Analyst — Repository Inventory Audit (TASK 44)

## 1. File & Directory Inventory
* **Repository Root**: `/Users/deneme/Desktop/llmprojesi`
* **Python Source & Test Files**: 953 files
* **TypeScript / TSX Files**: 112 files
* **Markdown Architectural & Technical Docs**: 84 files
* **JSON Configuration & Artifacts**: 1,382 files
* **Total Audited Code / Configuration Files**: 4,547 files

---

## 2. Directory Structure Breakdown

```text
llmprojesi/
├── backend/
│   ├── alembic/                      # Database migrations (26 linear versions)
│   │   └── versions/                 # fb1dbee3e894 -> b2c3d4e5f6a8 (head)
│   ├── app/                          # Core FastAPI platform modules (49 packages)
│   │   ├── agents/                   # 10-state Agent FSM, tools, checkpoints, memory
│   │   ├── analyst/                  # Multi-source AI Analyst coordination & synthesis
│   │   ├── api/v1/                   # 238 unique API paths, 289 endpoints
│   │   ├── auth/                     # JWT rotation, HttpOnly cookies, CSRF
│   │   ├── chunking/                 # Token-aware semantic document chunkers
│   │   ├── compliance/               # Controls, audit logs, PII, data retention
│   │   ├── connectors/               # Postgres, MySQL, CSV, Excel data connectors
│   │   ├── continuous_evaluation/    # Quality gates, ground-truth scorecards
│   │   ├── core/                     # Config, logging, exceptions, middleware
│   │   ├── db/                       # Postgres engine, Redis client, Qdrant client
│   │   ├── documents/                # File upload, storage, metadata extraction
│   │   ├── embeddings/               # Dense vector embeddings, caching
│   │   ├── evaluation/               # Metrics (Recall@5, Precision, Faithfulness)
│   │   ├── finops/                   # Usage ledger, model pricing, budget hard caps
│   │   ├── governance/               # Human approval quorum, risk scoring, TOCTOU
│   │   ├── ingestion/                # PDF, DOCX, CSV, XLSX multi-stage ingestion
│   │   ├── jobs/                     # Distributed workers, task FSM, dead-letter queue
│   │   ├── knowledge_graph/          # NetworkX multi-hop entity traversal
│   │   ├── llm_gateway/              # Multi-provider routing, circuit breakers, fallback
│   │   ├── memory/                   # Short-term, working, episodic, semantic memory
│   │   ├── models/                   # 114 SQLAlchemy declarative database models
│   │   ├── observability/            # OpenTelemetry, W3C traceparent, Prometheus
│   │   ├── product/                  # Production health, manifest, readiness scoring
│   │   ├── query/                    # Query understanding, intent decomposition
│   │   ├── rag/                      # Dense + BM25 Reciprocal Rank Fusion (RRF)
│   │   ├── rbac/                     # Role-permission matrices (Admin, Analyst, Viewer)
│   │   ├── reliability/              # Chaos fault injection, MTTR automated recovery
│   │   ├── reports/                  # Markdown, HTML, CSV, PDF export engine
│   │   ├── repositories/             # Database access repositories with tenant filters
│   │   ├── reranking/                # Cross-encoder reranker models
│   │   ├── response_orchestration/   # Streaming response synthesis & confidence
│   │   ├── retrieval/                # Sparse lexical and dense vector searchers
│   │   ├── security/                 # STRIDE defenses, prompt injection, SSRF shields
│   │   ├── semantic/                 # Business terms, metrics, column mappings
│   │   ├── services/                 # Business logic orchestrators
│   │   ├── sql_agent/                # Safe AST SQL validator and read-only executor
│   │   ├── sre/                      # SLI/SLO mathematics, error budget burn rates
│   │   ├── storage/                  # Local and S3 object storage providers
│   │   ├── tenancy/                  # Multi-tenant context and organization isolation
│   │   ├── tools/                    # Sandboxed computational analytics tools
│   │   ├── vectorstore/              # Qdrant client abstraction & collection management
│   │   └── workers/                  # Celery/Redis background worker processes
│   ├── scripts/                      # Seed, demo, reset, and audit CLI utilities
│   └── tests/                        # 24 test suites, 288 subsystem regressions
├── frontend/
│   ├── app/                          # Next.js 16 App Router (37 certified routes)
│   │   ├── (auth)/login/             # Dedicated authentication screen
│   │   ├── (dashboard)/              # AppShell wrapper (Collapsible Sidebar + Topbar)
│   │   │   ├── analyst/              # Dual-pane AI Analyst research workspace
│   │   │   ├── approvals/            # Human-in-the-loop risk approval quorum
│   │   │   ├── datasets/             # Dataset & document ingestion workspace
│   │   │   ├── evaluation/           # Continuous evaluation radar & trend charts
│   │   │   ├── executions/           # Execution timeline & event replay
│   │   │   ├── finops/               # FinOps cost hub, spend charts, budget dials
│   │   │   ├── operations/           # SRE SLOs, error budgets, and chaos reliability
│   │   │   ├── security/             # Security posture, findings, access reviews
│   │   │   ├── semantic/             # Semantic catalog, terms, metrics, graph
│   │   │   ├── settings/             # Organization profile & preferences
│   │   │   ├── showcase/             # Interactive Architecture & Portfolio Tour
│   │   │   └── page.tsx              # Overview Dashboard (KPIs, Recharts trends)
│   │   └── globals.css               # Craft dark theme tokens (#09090b), animations
│   ├── components/                   # UI atoms, layout, finops, compliance, common
│   ├── contexts/                     # LanguageContext (bilingual TR / EN)
│   ├── features/                     # Domain modules (analyst, evidence, auth)
│   ├── lib/                          # API client, SSE streaming client, TanStack Query
│   └── tests/                        # Vitest unit & RTL integration tests (25 tests)
├── docs/                             # Exhaustive engineering documentation
│   ├── architecture/                 # Blueprints & technical specifications
│   ├── audit/                        # System audit reports (TASK 44)
│   ├── compliance/                   # Compliance framework specifications
│   ├── deployment/                   # Docker Compose & production configurations
│   ├── finops/                       # Cost governance & pricing specifications
│   ├── operations/                   # SRE runbooks & SLO definitions
│   ├── product/                      # Showcase scripts & validation manifests
│   ├── reliability/                  # Chaos scenarios & disaster recovery drills
│   └── security/                     # STRIDE threat model & penetration tests
└── infra/                            # Docker Compose, Prometheus, Grafana, Traefik
```

---

## 3. Database Inventory Summary
* **Registered SQLAlchemy Models**: 114 tables
* **Tenant-Scoped Tables**: 99 tables (`organization_id` foreign key and indexes)
* **Global Tables**: 15 tables (`organizations`, `users`, `permissions`, `refresh_tokens`, `model_pricing`, `dataset_columns`, `analysis_steps`, `orchestration_steps`, `messages`, etc.)
* **Alembic Migrations**: 26 versions, unified linear chain to `b2c3d4e5f6a8 (head)`.

---

## 4. API Surface Inventory
* **Total Registered API Endpoints**: 289 (238 unique paths across `GET`, `POST`, `PUT`, `DELETE`).
* **OpenAPI Documentation**: Available at `/api/v1/docs` and `/api/v1/openapi.json`.
* **Frontend Routes**: 37 Next.js App Router paths compiled cleanly via Turbopack.

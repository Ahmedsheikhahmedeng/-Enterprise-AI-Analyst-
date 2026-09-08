# Enterprise AI Analyst — Backend Foundation, Infrastructure, Data & Auth Architecture

> Tasks 0, 1, 2, 3 & 4: Production-oriented FastAPI backend with asynchronous PostgreSQL, Redis, Qdrant infrastructure connectivity, health probes, SQLAlchemy 2 ORM domain models, Alembic migrations, and Argon2id/JWT identity authentication with refresh token rotation and reuse detection.

---

## 🏗️ Architecture Baseline

This backend service strictly adheres to the architectural blueprint defined in [docs/architecture/task_0_backend_architecture.md](../docs/architecture/task_0_backend_architecture.md).

---

## 🗄️ PostgreSQL Data Model & Alembic Migrations (Task 3)

### 1. Domain Entities (19 Models)

The relational data model is built using modern **SQLAlchemy 2 (`Mapped[]`, `mapped_column()`, `relationship()`)** with strict UUID primary keys and timezone-aware timestamps (`TIMESTAMP WITH TIME ZONE`):

| Domain Area | Table Name | Key Attributes & Constraints |
| :--- | :--- | :--- |
| **Tenancy & IAM** | `organizations` | `slug` (unique), `name`, `is_active` |
| | `users` | `email` (unique), `password_hash`, `first_name`, `last_name` |
| | `roles` | Scoped to `organization_id`, `name`, `description` |
| | `permissions` | `name` (unique, e.g. `documents.read`, `reports.create`) |
| | `role_permissions` | Composite PK (`role_id`, `permission_id`) association table |
| | `organization_members` | Composite unique (`organization_id`, `user_id`), assigned `role_id` |
| **Unstructured Data** | `documents` | Scoped to `organization_id`, file metadata, `status`, indexed on `(organization_id, created_at)` |
| | `document_chunks` | Scoped to `organization_id`, `document_id`, `chunk_index`, text content, `metadata` (JSONB) |
| **Structured Data** | `datasets` | Scoped to `organization_id`, `source_type`, `status`, `row_count` |
| | `dataset_columns` | Composite unique (`dataset_id`, `name`), `data_type`, `ordinal_position` |
| | `data_sources` | Scoped to `organization_id`, `type`, `status`, `configuration` (JSONB) |
| **AI Conversations** | `conversations` | Scoped to `organization_id`, `user_id`, `title`, indexed on `(organization_id, created_at)` |
| | `messages` | Linked to `conversation_id`, `role` (`user`/`assistant`/`tool`), indexed on `(conversation_id, created_at)` |
| **Analysis Engine** | `analysis_runs` | Scoped to `organization_id`, optional `conversation_id`, `query`, status, timestamps |
| | `analysis_steps` | Linked to `analysis_run_id`, composite unique `(analysis_run_id, step_order)`, JSONB payloads |
| **Outputs & Auditing** | `reports` | Scoped to `organization_id`, generated markdown/JSON content, links to `analysis_run_id` |
| | `audit_logs` | Append-only tenant audit stream (`organization_id`, `user_id`, `action`, `resource_type`, `metadata`) |
| | `usage_events` | Granular operational events (`organization_id`, `event_type`, `quantity`, `metadata`) |
| | `llm_requests` | Cost and latency tracking per LLM inference (`model`, tokens, `estimated_cost`, `latency_ms`) |

### 2. Multi-Tenant Architecture
- Every tenant-owned table explicitly includes `organization_id` (foreign key to `organizations.id` with `ON DELETE RESTRICT` or `CASCADE` depending on business domain).
- Global/system resources (`users`, `permissions`) remain outside direct tenant scoping; user membership is maintained through `organization_members`.
- Queries enforce multi-tenant isolation through composite indexes such as `(organization_id, created_at)`.

---

## 🔐 Authentication System (Task 4)

The authentication system is dedicated strictly to **identity verification** (who the user is). RBAC and tenant-level authorization remain separated into Tasks 5 and 6.

### 1. Security Architecture
- **Argon2id Hashing**: Passwords are never stored or logged in plaintext. Baseline policy enforces $\ge 8$ characters.
- **Short-Lived JWT Access Tokens**: 15-minute lifespan (`ACCESS_TOKEN_EXPIRE_MINUTES`), containing `sub` (User UUID), `type: "access"`, `iat`, `exp`, and `jti`.
- **Hashed Refresh Token Sessions**: Refresh tokens are stored strictly as SHA-256 digests in PostgreSQL (`refresh_tokens`). Plaintext tokens exist only transiently at issuance time.
- **Token Rotation & Token Family Tracking**: Every refresh operation revokes the presented token and creates a new token session linked via `rotated_from_id` within a persistent `family_id`.
- **Reuse Detection**: Presenting an already-revoked refresh token triggers a security alert and immediately revokes the entire token family lineage, preventing session hijacking.
- **Enumeration Protection**: Registration and login endpoints emit generic error messages to prevent email enumeration.

### 2. API Endpoints

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register a new user with Argon2id hash | No |
| `POST` | `/api/v1/auth/login` | Authenticate email/password, emit JWT + refresh token | No |
| `GET` | `/api/v1/auth/me` | Fetch authenticated caller profile (sanitized) | Yes (`Bearer`) |
| `POST` | `/api/v1/auth/refresh` | Rotate refresh token session, emit new token pair | No |
| `POST` | `/api/v1/auth/logout` | Revoke specific refresh token session | No |
| `POST` | `/api/v1/auth/logout-all` | Revoke all active refresh sessions for user | Yes (`Bearer`) |
| `POST` | `/api/v1/auth/change-password` | Update password and invalidate all active sessions | Yes (`Bearer`) |
| `POST` | `/api/v1/auth/forgot-password` | Issue single-use password reset token | No |
| `POST` | `/api/v1/auth/reset-password` | Consume reset token and set new password | No |
| `POST` | `/api/v1/auth/verify-email` | Confirm email with single-use verification token | No |
| `POST` | `/api/v1/auth/resend-verification` | Re-issue single-use verification token | No |

### 3. Environment Configuration
```env
JWT_SECRET_KEY="generate-a-secure-random-64-character-hex-key-for-production"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=60
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=24
```
*(In production, `JWT_SECRET_KEY` must be explicitly configured with at least 32 characters.)*

---

## 🛡️ Role-Based Access Control (RBAC) & Authorization (Task 5)

The authorization layer answers: **"What is this authenticated user allowed to do?"**
It builds on the authentication from Task 4 while maintaining strict architectural decoupling.

### 1. Authorization Architecture

```text
HTTP Request
     │
     ▼
[Authentication] ───► get_current_user (JWT Bearer Token validation)
     │                └── Yields 401 Unauthorized if missing, malformed, or expired
     ▼
[Context Resolution] ───► resolve_organization_context (via X-Organization-ID header)
     │                    └── Resolves single org or yields 403 Forbidden
     ▼
[Permission Check] ───► require_permission("documents.read")
     │                  └── Queries effective permissions in single SQL query
     │                  └── Yields 403 Forbidden with generic contract if unauthorized
     ▼
[Route Execution] ───► Service / Repository Layer
```

### 2. System Permission Catalog (26 Permissions)

| Category | Permissions | Description |
| :--- | :--- | :--- |
| **Users** | `users.read`, `users.manage`, `users.invite`, `users.remove` | User directory and administrative membership management |
| **Organization** | `organization.read`, `organization.manage` | Organization settings and configuration |
| **Documents** | `documents.read`, `documents.write`, `documents.delete`, `documents.manage` | Document upload, download, deletion, and pipeline administration |
| **Datasets** | `datasets.read`, `datasets.write`, `datasets.delete` | Structured data schemas and records management |
| **Data Sources** | `data_sources.read`, `data_sources.write`, `data_sources.delete` | External database and integration connectors |
| **Reports** | `reports.read`, `reports.create`, `reports.update`, `reports.delete` | Enterprise report generation, viewing, and deletion |
| **Analytics** | `analytics.read`, `analytics.execute` | Analytic metrics and query executions |
| **AI** | `ai.chat`, `ai.analyze` | Interactive chat and deep autonomous AI analysis |
| **Audit & Usage** | `audit.read`, `usage.read` | Organization audit logging and token consumption inspection |

### 3. Role Definitions & Default Mappings

- **`Admin`**: Full access to all 26 permissions across users, organization, data, AI, and audit.
- **`Analyst`**: Operational analytics and AI: `organization.read`, `documents.read/write`, `datasets.read/write`, `data_sources.read`, `reports.read/create`, `analytics.read/execute`, `ai.chat/analyze`.
- **`Viewer`**: Read-only visibility: `organization.read`, `documents.read`, `datasets.read`, `reports.read`, `analytics.read`, `ai.chat`.

### 4. Security Principles & Enforcement
- **401 vs 403**: Unauthenticated, invalid, or expired tokens always yield `401 Unauthorized`. Authenticated users lacking required permissions or valid tenant membership always yield `403 Forbidden`.
- **Generic Error Contract**: Authorization denial responses never leak required permission names:
  `{"error": {"code": "FORBIDDEN", "message": "You do not have permission to perform this action.", "request_id": "..."}}`
- **Context-Scoped Permissions**: A user can belong to multiple organizations with different roles (e.g. Analyst in Org A, Viewer in Org B). Permissions are strictly evaluated against the target organization context.
- **Cross-Organization Protection**: Roles scoped to Organization B cannot grant permissions to a member in Organization A.
- **No N+1 Queries**: Effective permissions are retrieved with a single joined query across `permissions`, `role_permissions`, `roles`, and `organization_members`.
- **Structured Audit Logging**: Authorization denials and role assignments/removals emit structured audit logs (`audit_event="role_assigned"`, `audit_event="authorization_denied"`) without logging sensitive secrets.

### 5. RBAC Seeding
Seed system permissions, roles, and default mappings idempotently:
```bash
python scripts/seed_rbac.py
```

### 6. Demonstration & Management Endpoints

| Method | Endpoint | Required Permission | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/admin/users` | `users.manage` | Admin user management access demonstration |
| `GET` | `/api/v1/rbac/test/read-document` | `documents.read` | Document read access demonstration |
| `POST` | `/api/v1/rbac/test/create-report` | `reports.create` | Report creation access demonstration |
| `GET` | `/api/v1/rbac/permissions` | Authenticated | Inspect caller's effective permissions for active organization |
| `GET` | `/api/v1/rbac/roles` | `organization.read` | List available system and organization roles |
| `POST` | `/api/v1/rbac/roles/assign` | `users.manage` | Assign or update member role in organization |
| `POST` | `/api/v1/rbac/roles/remove` | `users.manage` | Remove member role and membership in organization |


---

## 🏢 Multi-Tenant Authorization & Isolation (Task 6)

The multi-tenant authorization layer establishes complete tenant isolation:
**A user belonging to Organization A can never read, modify, delete, count, list, or infer resources belonging to Organization B.**

### 1. The 5-Layer Authorization Pipeline

To access any protected tenant resource, the request must successfully traverse all 5 layers:
```text
HTTP Request (Header: Authorization Bearer <token>, X-Organization-ID <uuid>)
     │
     ▼
1. [User Authentication]        ───► get_current_user (JWT decoded, active user) -> 401 if invalid
     │
     ▼
2. [Organization Validation]    ───► Exists in DB and is_active == True -> 403 if missing or inactive
     │
     ▼
3. [Membership & Role Validation]───► User is member, role belongs to org -> 403 if non-member or role mismatch
     │
     ▼
4. [Permission Enforcement]     ───► require_tenant_permission(perm) (effective permissions) -> 403 if unauthorized
     │
     ▼
5. [Resource Tenant Enforcement]───► WHERE id = :id AND organization_id = :org_id -> 404 if cross-tenant (anti-IDOR)
```

### 2. Tenant Context (`TenantContext`)

A request-scoped, immutable data structure injected via `get_current_tenant`:
```python
@dataclass(frozen=True, slots=True)
class TenantContext:
    organization_id: uuid.UUID
    user_id: uuid.UUID
    membership_id: uuid.UUID
    role_id: uuid.UUID
    role_name: str
    permissions: frozenset[str]
```

### 3. Tenant Context Resolution Flow
1. **`X-Organization-ID` Header**: Sanitized and parsed as a UUID. Malformed UUIDs are rejected immediately (`422 Unprocessable Content`) without querying the database.
2. **Single-Membership Fallback**: If no header is provided and the user has exactly 1 membership, that organization is automatically used.
3. **Ambiguous Context Rejection**: If the user belongs to multiple organizations and does not provide `X-Organization-ID`, access is securely rejected (`403 Forbidden`, `code="AMBIGUOUS_TENANT_CONTEXT"`).
4. **Empty Membership Rejection**: Users with 0 memberships are rejected with `403 Forbidden`.

### 4. Tenant-Scoped Repositories (`TenantScopedRepository[ModelType]`)

All tenant-owned resource queries **must** pass through tenant-scoped repositories:
- `get_by_id(session, id, organization_id)`: Appends `WHERE organization_id = :org_id`
- `list(session, organization_id, skip, limit)`: Filters by `organization_id` **before** pagination
- `count(session, organization_id)`: Scopes count strictly to tenant
- `create(session, organization_id, **kwargs)`: Discards untrusted payload `organization_id` and binds strictly to trusted `TenantContext.organization_id`
- `update(session, id, organization_id, **values)`: Updates only where both `id` and `organization_id` match; verifies rowcount
- `delete(session, id, organization_id)`: Deletes only where both `id` and `organization_id` match; verifies rowcount

### 5. Nested Resource Security

For hierarchical resources (e.g. `DocumentChunk` within `Document`):
Both the chunk and parent document must belong to the caller's organization, and `chunk.document_id == document_id`. Attempting to access `chunk_A` under `document_B` is rejected with `404 Not Found`.

### 6. The 404 vs 403 Security Strategy
- **Why 404 for cross-tenant resource lookups?** If User A queries `GET /api/v1/tenant/documents/{doc_B_id}`, returning `403 Forbidden` would confirm to the attacker that `doc_B_id` exists. Returning `404 Not Found` treats foreign resources as nonexistent, completely preventing resource enumeration and IDOR attacks.
- **When is 403 returned?** When the user attempts to claim an organization context they do not belong to, or attempts an action their role lacks permission for.

### 7. Evaluation of PostgreSQL Row-Level Security (RLS)
The platform currently enforces tenant boundaries at the repository and service layer through:
- Compulsory `organization_id` foreign keys and composite indexes on all tenant models (`TenantScopedMixin`).
- Mandatory `TenantScopedRepository` query patterns where `organization_id` cannot be omitted.
- Rowcount assertions on mutations.
*Note on RLS:* Application-level enforcement allows clear API-level error envelopes (`404` vs `403`) and audit logging. PostgreSQL RLS using `SET LOCAL app.current_tenant_id` can be added as an optional defense-in-depth layer in future operations without breaking repository contracts.

### 8. Qdrant Vector Isolation Preparation
Vector retrieval is isolated at query generation time using `build_qdrant_tenant_filter(organization_id)`. All future semantic vector searches must apply this mandatory payload filter condition.

### 9. Tenant API Demonstration Endpoints

| Method | Endpoint | Permission Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/tenant/context` | Authenticated | Inspect caller's resolved `TenantContext` |
| `POST` | `/api/v1/tenant/documents` | `documents.write` | Create a document strictly bound to active tenant |
| `GET` | `/api/v1/tenant/documents` | `documents.read` | List tenant documents (scoped pagination) |
| `GET` | `/api/v1/tenant/documents/count` | `documents.read` | Count tenant documents |
| `GET` | `/api/v1/tenant/documents/{id}` | `documents.read` | Fetch document by ID (anti-IDOR 404 on cross-tenant) |
| `PUT` | `/api/v1/tenant/documents/{id}` | `documents.write` | Update document (tenant-scoped) |
| `DELETE` | `/api/v1/tenant/documents/{id}` | `documents.delete` | Delete document (tenant-scoped) |
| `GET` | `/api/v1/tenant/documents/{doc_id}/chunks/{chunk_id}` | `documents.read` | Nested chunk traversal validation |

---

## 📁 File Storage & Document Management Foundation (Task 7)

Task 7 establishes a secure, enterprise-grade storage and document management layer that prepares the platform for future ingestion, chunking, and embedding pipelines without implementing parsing, RAG, or vector operations.

### 1. Storage Architecture & Provider Abstraction

The storage layer is completely decoupled from database models and REST handlers via the abstract `StorageProvider` interface:

```text
HTTP Request (POST /api/v1/documents)
     │
     ▼
[Document Router] ───► Validates RBAC & TenantContext
     │
     ▼
[Document Service] ───► Streaming SHA-256 + MIME detection + Tenant Deduplication
     │
     ├───────────────► StorageProvider (Abstraction)
     │                     ├── LocalStorageProvider (Development / On-Prem)
     │                     └── S3StorageProvider (Production: AWS S3, MinIO, Cloudflare R2)
     ▼
[Document Repository] ──► Persists Document Metadata in PostgreSQL (Tenant-Scoped)
```

- **`LocalStorageProvider`**: Stores files locally under `storage/organizations/{organization_id}/documents/{object_key}`. Uses safe path resolution, atomic writes via temporary files, and chunked streaming.
- **`S3StorageProvider`**: Production adapter for S3-compatible object stores (AWS S3, MinIO, Cloudflare R2). Strictly enforces private buckets, server-side access only, and no public URLs.

### 2. Supported File Types & MIME Detection

The platform supports 5 enterprise file formats. Extension alone is not trusted; content is validated against binary magic bytes:

| Extension | Declared MIME | Signature Validation (Magic Bytes) |
| :--- | :--- | :--- |
| `.pdf` | `application/pdf` | Must begin with `%PDF-` header signature |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Must begin with `PK\x03\x04` ZIP archive header |
| `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | Must begin with `PK\x03\x04` ZIP archive header |
| `.txt` | `text/plain` | Valid UTF-8 text, rejects binary null bytes (`\x00`) |
| `.csv` | `text/csv` | Valid UTF-8 text, rejects binary null bytes (`\x00`) |

Unsupported extensions or mismatched signatures are rejected with `422 Unprocessable Content`.

### 3. File Size Limit & Streaming Upload

- Configurable via `MAX_UPLOAD_SIZE_MB` (default: `25 MB`).
- Uploads are processed in 64 KB chunks into a `SpooledTemporaryFile` (512 KB in RAM before spooling to disk), computing the SHA-256 digest on the fly.
- Arbitrary large payloads exceeding the limit immediately abort with `413 Content Too Large`.
- 0-byte (empty) files are rejected with `422 Unprocessable Content` (`code="EMPTY_FILE"`).

### 4. Tenant-Scoped Checksum & Duplicate Detection

- Checksums are calculated as 64-character hex-encoded SHA-256 strings.
- **Deduplication Policy**: Scoped strictly to `(organization_id, sha256)`. If an active document with an identical checksum exists for the same organization, the upload is rejected with `409 Conflict` (`code="DUPLICATE_DOCUMENT"`) and includes the existing document ID.
- Separate organizations may legitimately upload identical documents without conflict; cross-tenant deduplication is strictly avoided.
- A PostgreSQL partial unique index (`uq_documents_org_sha256_active`) guarantees duplicate protection against concurrent race conditions.

### 5. Document Lifecycle Status

The document model supports the full enterprise ingestion lifecycle:
- `uploaded`: File validated, stored, and metadata committed (active in Task 7).
- `processing`: Document queued for extraction (future).
- `parsed`: Content extracted and normalized (future).
- `chunking`: Document split into chunks (future).
- `embedding`: Vector embeddings generated (future).
- `indexed`: Document indexed in Qdrant (future).
- `failed`: Validation or ingestion failure (active in Task 7).
- `deleted`: Soft-deleted; excluded from normal queries and physical storage purged (active in Task 7).

### 6. Atomic Storage & Consistency Strategy

- Files are written to the storage provider before database commit.
- If the database insertion, flush, or transaction commit fails, the uploaded object is immediately deleted from storage in the exception handler (`storage_orphan_cleanup`), guaranteeing no orphaned storage objects.
- If storage write fails, the database transaction is rolled back and no row is created.

### 7. Security & Sanitization

- **Path Traversal Defense**: All storage keys are server-controlled (`organizations/{org_id}/documents/{uuid}.{ext}`). User-supplied filenames are never used in filesystem paths. Any path traversal sequences (`..`, absolute paths) are neutralized and rejected (`code="PATH_TRAVERSAL_DETECTED"`).
- **Filename Sanitization**: Original filenames are preserved as metadata only. Basenames are extracted, Windows/POSIX separators normalized, and carriage returns/newlines stripped to prevent CRLF header injection.
- **Safe Download Headers**:
  - `Content-Disposition: attachment; filename="{clean_name}"; filename*=UTF-8''{encoded_name}`
  - `Content-Length: {size}`
  - `X-Content-Type-Options: nosniff`
- **Secrets & Privacy**: Storage credentials, storage keys, and raw file contents are never emitted in logs or public API responses.

### 8. Document REST Endpoints (`/api/v1/documents`)

| Method | Endpoint | Permission Required | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/documents` | `documents.write` | Multipart form upload (streaming validation, deduplication, atomic write) |
| `GET` | `/api/v1/documents` | `documents.read` | List tenant documents (paginated via `skip` and `limit`) |
| `GET` | `/api/v1/documents/{id}` | `documents.read` | Get document metadata (tenant-isolated; 404 for other tenants) |
| `GET` | `/api/v1/documents/{id}/download` | `documents.read` | Stream document content with RFC 5987 sanitized download headers |
| `DELETE` | `/api/v1/documents/{id}` | `documents.delete` | Soft-delete document metadata and purge storage object |

### 9. Environment Configuration
```env
STORAGE_BACKEND="local"          # Options: "local", "s3"
LOCAL_STORAGE_ROOT="storage"     # Base directory for local filesystem storage
MAX_UPLOAD_SIZE_MB=25            # Maximum upload size limit

# S3 Configuration (Required only when STORAGE_BACKEND="s3")
S3_ENDPOINT_URL=""               # Optional (e.g. MinIO, Cloudflare R2, LocalStack)
S3_BUCKET="enterprise-documents"
S3_REGION="us-east-1"
S3_ACCESS_KEY_ID=""
S3_SECRET_ACCESS_KEY=""
```

---


## 📦 Backing Infrastructure Services (Task 2)

| Service | Engine Version | Role in Architecture |
| :--- | :--- | :--- |
| **PostgreSQL** | `16-alpine` | Primary transactional and relational store for users, orgs, datasets, and audits. |
| **Redis** | `7-alpine` | High-speed cache, distributed rate limiting, and async broker. |
| **Qdrant** | `latest` | High-performance vector database powering dense and sparse hybrid retrieval. |

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites
- Python 3.12+
- Docker & Docker Compose (for local containerized infrastructure)

### 2. Environment Configuration
Copy the sample environment configuration:
```bash
cp .env.example .env
```

### 3. Install Python Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

### 4. Docker Compose Operations
Start all backing infrastructure services and backend container:
```bash
docker compose up --build -d
```

Check container status and health probes:
```bash
docker compose ps
```

View aggregated service logs:
```bash
docker compose logs -f
```

Stop containers gracefully:
```bash
docker compose down
```

Stop containers and remove persistent volumes (resets PostgreSQL and Qdrant data):
```bash
docker compose down -v
```

### 5. Running Natively (Without Containerized Backend)
If backing services are running natively or in standalone containers:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🩺 Health Check Endpoints

| Endpoint | Purpose | Semantics |
| :--- | :--- | :--- |
| `GET /api/v1/health` | Basic Service Health | Backward-compatible baseline health returning service name and version. |
| `GET /api/v1/health/live` | Liveness Probe | Indicates the application event loop is alive and responsive. |
| `GET /api/v1/health/ready` | Readiness Probe | Evaluates reachability of **PostgreSQL**, **Redis**, and **Qdrant**. Returns `200 OK` when all dependencies are reachable, or `503 Service Unavailable` if any dependency is offline. |

---

## 🗃️ Database Migrations (Alembic)

Run database migrations to latest schema version:
```bash
alembic upgrade head
```

Rollback the most recent migration step:
```bash
alembic downgrade -1
```

Generate a new migration script following model changes:
```bash
alembic revision --autogenerate -m "describe_changes"
```

---

## 📑 Document Ingestion Pipeline (Task 8)

The Document Ingestion Pipeline transforms securely stored files into a normalized, structured canonical document representation that is ready for intelligent chunking (Task 9).

### 1. Ingestion Pipeline Architecture

```text
Stored File (StorageProvider)
     │
     ▼
Ingestion Job (IngestionWorker / IngestionService)
     │
     ▼
Parser Resolver (MIME / Detected Signature / Extension)
     │
     ▼
Document Parser (PDF, DOCX, TXT, CSV, XLSX)
     │
     ▼
Normalization Layer (Unicode NFC, Line Endings, Whitespace, Control Characters)
     │
     ▼
Structure & Metadata Extraction (Pages, Sections, Tables, Sheets, Word/Char Counts)
     │
     ▼
Canonical Parsed Document (ParsedDocument Domain Model)
     │
     ▼
Persistence:
 ├── Object Storage: organizations/{org_id}/documents/{doc_id}/parsed.json
 └── PostgreSQL: metadata, page_count, parser_name, parser_version, status = "parsed"
```

### 2. Supported File Types & Parser Layer

| Extension | Detected MIME Types | Parser Engine | Structural Preservation |
| :--- | :--- | :--- | :--- |
| `.pdf` | `application/pdf`, `application/x-pdf` | `pypdf` | Physical page boundaries, outline bookmarks as headings, tabular columns |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | `python-docx` | Sequential body element ordering, headings (H1-H6), bullet/numbered lists, tables |
| `.txt`, `.md` | `text/plain`, `text/markdown` | `builtin-txt` | Paragraph boundaries, markdown headings, bullet lists, UTF-8 multilingual characters |
| `.csv` | `text/csv`, `application/csv` | `builtin-csv` | Grid structure, column headers, rows, empty cells, auto-sniffed delimiters (`,`, `;`, `\t`, `\|`) |
| `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `openpyxl` | Multi-sheet workbooks (unmerged), headers, rows, empty cell preservation |

### 3. Canonical Parsed Document Representation

The downstream system interacts with a strongly-typed, decoupled canonical data model (`app.ingestion.models.ParsedDocument`):

- **`ParsedDocument`**: Top-level representation containing `document_id`, `title`, `source_type`, `parser_name`, `parser_version`, `pages`, `sections`, `tables`, and `metadata`.
- **`ParsedPage`**: Preserves physical page numbers and page-level block collections for paginated formats.
- **`ParsedSection`**: Preserves hierarchical logical sections (`level`, `title`, `blocks`).
- **`ParsedBlock`**: Atomic block element categorized by `BlockType` (`heading`, `paragraph`, `list`, `table`, `other`).
- **`ParsedTable`**: Structured grid preserving `headers`, `rows`, `page_number`, and `sheet_name` without flattening into unstructured paragraphs.

### 4. Text & Structural Normalization

The normalization layer (`app.ingestion.normalization`) enforces deterministic document hygiene without altering semantic content:
- **Unicode NFC Normalization**: Standardizes Unicode representation while safely preserving Arabic, Turkish (`ç, ğ, ı, ö, ş, ü, İ`), diacritics, and currency symbols.
- **Line Ending Normalization**: Converts `\r\n` and `\r` to standard `\n`.
- **Whitespace Hygiene**: Collapses duplicate horizontal spaces/tabs and caps vertical blank lines at two consecutive newlines.
- **Control Character Stripping**: Strips dangerous non-printable ASCII/Unicode control characters while preserving formatting whitespace.

### 5. Ingestion Status Transitions & Failure Handling

Documents strictly transition through the following states during Task 8:
- `uploaded`: Document stored; awaiting ingestion.
- `processing`: Document currently being retrieved, parsed, and normalized.
- `parsed`: Ingestion completed successfully; canonical JSON artifact persisted and metadata updated.
- `failed`: Parsing or resource limit failure; safe concise `failure_reason` recorded.

**Security & Error Isolation:**
- Stack traces and file system paths are **never** returned to API clients or stored in user-visible `failure_reason`.
- Corrupted documents, malformed CSVs, and encrypted PDFs fail safely with controlled error descriptions.
- The pipeline is completely idempotent: repeated ingestion of the same document overwrites the canonical storage artifact and updates metadata deterministically without creating duplicate database rows.

### 6. Resource Limits & Archive Safety

Configurable limits guard worker memory and compute against denial-of-service payloads:
```env
MAX_INGESTION_PAGES=500
MAX_INGESTION_ROWS=50000
MAX_INGESTION_SHEETS=20
MAX_EXTRACTED_CHARACTERS=5000000
AUTO_INGEST=true
```
- OpenXML archives (`.docx`, `.xlsx`) are read strictly through trusted libraries with streaming/read-only mode (`openpyxl(read_only=True, data_only=True)`), preventing decompression bombs and memory spikes.

### 7. API Endpoints

| Method | Endpoint | Description | Permission |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/documents` | Upload document; enqueues ingestion job if `AUTO_INGEST=true` | `documents.write` |
| `POST` | `/api/v1/documents/{id}/ingest` | Trigger or reprocess ingestion (supports `?sync=true`) | `documents.write` |
| `GET` | `/api/v1/documents/{id}/parsed` | Retrieve canonical parsed document representation | `documents.read` |

---

## 📊 Enterprise Report Generation & Export (Task 19)

Transforms synthesized `AIAnalystService` results into structured, versioned, verifiable, and exportable intelligence documents:

- **Structured Report Model (`ReportDocument`)**: Executive summary, key findings with citations, metrics, tables, chart metadata, unified evidence (`[S#]`, `[R#]`), data discrepancies/conflicts, and methodology.
- **Relational Persistence & Versioning**: Extends PostgreSQL `reports` model and introduces `report_versions` for transaction-safe version increments. Draft versions are mutable; published versions are permanently immutable.
- **Multi-Format Renderers & Exporters**:
  - **Markdown**: Clean, deterministic GitHub-Flavored Markdown.
  - **HTML**: Self-contained semantic HTML5 with inline CSS, strict XSS escaping, and RTL/LTR bidirectional support (Arabic, English, Turkish).
  - **PDF**: Paginated A4 output via `reportlab` with dynamic page numbers (`Page X of Y`), running headers, and conflict callouts.
  - **CSV**: Strictly exports verified `ReportTable` rows and metrics without arbitrary database access.
- **Security & RBAC**: Tenant-scoped authorization (`reports.read`, `reports.create`, `reports.update`, `reports.publish`, `reports.export`, `reports.archive`), directory traversal sanitization, and structured audit logging (`report.created`, `report.published`, etc.).

### Report Endpoints (`/api/v1/reports`)

| Method | Endpoint | Description | Permission |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/reports/from-analysis` | Synthesize new report draft from `analysis_run_id` | `reports.create` |
| `GET` | `/api/v1/reports` | List paginated reports for tenant | `reports.read` |
| `GET` | `/api/v1/reports/{id}` | Get report metadata and latest version | `reports.read` |
| `GET` | `/api/v1/reports/{id}/versions/{v}` | Get specific historical version | `reports.read` |
| `POST` | `/api/v1/reports/{id}/publish` | Transition report to immutable published status | `reports.publish` |
| `POST` | `/api/v1/reports/{id}/archive` | Archive an active report | `reports.archive` |
| `GET` | `/api/v1/reports/{id}/export/{format}` | Export report as `markdown`, `html`, `pdf`, or `csv` | `reports.export` |

---

## 🔬 Enterprise AI Evaluation & Quality Framework (Task 20)

Provides a reproducible, quantitative measurement subsystem validating the end-to-end analytical pipeline without altering production behavior:

- **Evaluation Dataset Management & Versioning**: Versioned datasets (`evaluation_datasets`, `evaluation_dataset_versions`) capturing immutable test cases and cryptographic checksums for historical reproducibility.
- **Multi-Modal Benchmark Cases (`EvaluationCase`)**: Structured ground-truth test cases across `sql`, `rag`, `hybrid`, and `none` routes.
- **Deterministic Information Retrieval Metrics**: Mathematical computation of Recall@K (1, 3, 5, 10), Precision@5, HitRate@K, MRR, and nDCG@5.
- **RAG & Faithfulness Metrics**: Context Recall, Context Precision, Answer Relevance, and claim-level Faithfulness.
- **SQL Safety & Numeric Accuracy**: Strict rejection of DDL/DML and multi-statement injection; numerical comparison against tolerances (`exact`, `0.1%`, `1%`, `5%`).
- **Grounding & Citation Verification**: Citation Precision, Recall, Coverage, and Phantom Citation Rate; Claim Groundedness (`fully_grounded`, `partially_grounded`, `ungrounded`).
- **Deterministic Hallucination Checks**: Detection of unsupported numeric claims, phantom citations, dates, and percentages.
- **Latency Percentiles & Cost Tracking**: Non-parametric percentile computation (P50, P75, P90, P95, P99); token and financial cost accounting per query and per 1,000 queries.
- **Multi-Dimensional Scorecard**: Aggregates results into isolated Quality, Performance, Cost, and Overall scores.
- **Regression Detection**: Automated comparative diffing between baseline and candidate benchmark runs with configurable regression thresholds.
- **Security & RBAC**: Tenant-scoped isolation, granular permissions (`evaluation.read`, `evaluation.create`, `evaluation.run`, `evaluation.compare`), and structured audit logging.

### Evaluation Endpoints (`/api/v1/evaluation`)

| Method | Endpoint | Description | Permission |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/evaluation/datasets` | Create benchmark dataset | `evaluation.create` |
| `GET` | `/api/v1/evaluation/datasets` | List datasets for tenant | `evaluation.read` |
| `POST` | `/api/v1/evaluation/datasets/{id}/cases` | Add benchmark case to dataset | `evaluation.create` |
| `GET` | `/api/v1/evaluation/datasets/{id}/cases` | List cases in dataset | `evaluation.read` |
| `POST` | `/api/v1/evaluation/runs` | Execute benchmark run against analyst pipeline | `evaluation.run` |
| `GET` | `/api/v1/evaluation/runs/{id}` | Get run details and progress | `evaluation.read` |
| `GET` | `/api/v1/evaluation/runs/{id}/results` | Get fine-grained case-level scores | `evaluation.read` |
| `GET` | `/api/v1/evaluation/runs/{id}/scorecard` | Get run scorecard (Quality, Perf, Cost) | `evaluation.read` |
| `POST` | `/api/v1/evaluation/runs/{id}/compare` | Compare candidate run against baseline | `evaluation.compare` |

---

## 📡 Production Observability, Distributed Tracing & Monitoring (Task 21)

Task 21 implements enterprise observability, distributed tracing, high-cardinality protection, and metrics exposition across HTTP, Analyst, SQL, RAG, and LLM layers.

### 1. Architecture Highlights
- **Immutable Context**: `ObservabilityContext` propagates `request_id`, `trace_id`, `span_id`, and tenant identity via `contextvars`.
- **W3C Trace Context**: Strict `traceparent` (`00-{trace_id}-{span_id}-{flags}`) parsing and header generation.
- **Hierarchical Spans**: `analyst.ask` coordinates nested spans for `plan`, `sql`, `rag`, `merge`, `conflict_detection`, and `final_generation`.
- **Central Redaction**: `TelemetryRedactor` sanitizes Bearer tokens, DB passwords, API keys, and secrets.
- **High-Cardinality Protection**: Labels strictly prohibit dynamic identifiers (`user_id`, `request_id`, `query`, `prompt`), throwing `HighCardinalityViolationError`.
- **Exporters**: Structured logging, Prometheus format (`/api/v1/observability/metrics`), and OpenTelemetry abstraction.
- **SLOs & Error Budgets**: Declarative targets (analyst availability, latency, SQL/RAG/LLM success rates) and deterministic error budget tracking.
- **Granular Health**: `/health/dependencies` and `/api/v1/observability/health` evaluating PostgreSQL, Redis, Qdrant, and LLM provider connectivity and latencies.

### 2. Endpoints

| Method | Path | Description | Required Permission |
| :--- | :--- | :--- | :--- |
| `GET` | `/health/dependencies` | Granular dependency health probes | Public / Internal |
| `GET` | `/api/v1/observability/summary` | Aggregated operational platform summary | `observability.read` |
| `GET` | `/api/v1/observability/metrics` | Prometheus exposition metrics stream | `observability.metrics` |
| `GET` | `/api/v1/observability/health` | Detailed dependency connectivity & latency | `observability.health` |
| `GET` | `/api/v1/observability/slos` | SLO compliance status & error budgets | `observability.read` |
| `GET` | `/api/v1/observability/alerts` | Operational alerts & anomaly scans | `observability.read` |
| `GET` | `/api/v1/observability/traces/{id}` | Distributed trace waterfall spans | `observability.read` |

---

## ⚡ Background Jobs & Distributed Worker Architecture (Task 23)

Production background job and distributed worker architecture transitioning heavy, long-running operations (`document_ingestion`, `chunking`, `embedding`, `vector_indexing`, `evaluation`, `report_export`) from synchronous HTTP cycles to an observable, resilient, multi-tenant queue/worker model with **at-least-once delivery** and idempotent task handlers.

### Key Capabilities
- **Reliable Queues**: Redis-backed queue (`RedisJobQueue`) with multi-priority levels (`high`, `normal`, `low`), in-flight reservation with visibility timeouts, delayed queues for exponential backoff, and thread-safe `InMemoryJobQueue` fallback.
- **Strict State Machine**: Fully validated transitions (`queued` $\to$ `running` $\to$ `completed` / `failed` / `retry_scheduled` / `cancelled` / `dead_letter`).
- **Deterministic Idempotency**: Canonical SHA-256 JSON hashing (`JobIdempotencyManager`) enabling transparent replay without duplicate processing, and rejecting conflicting payloads with HTTP 409.
- **Resilient Retries**: Exponential backoff with full jitter, classified into transient retryable errors vs non-retryable fatal errors.
- **Safe Cancellation**: In-memory and database checkpoints allow tasks to terminate cleanly between batch boundaries.
- **Worker Health & Stuck Detection**: Heartbeats recorded with TTL in Redis (`jobs:worker:{id}:heartbeat`) and automatic detection of stuck running jobs.
- **Tenant Isolation & RBAC**: Every job strictly isolated to `organization_id`; granular permissions (`jobs.read`, `jobs.create`, `jobs.cancel`, `jobs.retry`, `jobs.admin`).

### API Endpoints
| Method | Endpoint | Description | Required Permission |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/jobs` | Enqueue background job (returns 202 Accepted) | `jobs.create` |
| `GET` | `/api/v1/jobs/{job_id}` | Get job execution status, progress, diagnostics | `jobs.read` |
| `GET` | `/api/v1/jobs` | List organization jobs with pagination & filters | `jobs.read` |
| `POST` | `/api/v1/jobs/{job_id}/cancel` | Cancel pending or running job at safe checkpoint | `jobs.cancel` |
| `POST` | `/api/v1/jobs/{job_id}/retry` | Manually re-enqueue failed or dead-lettered job | `jobs.retry` |
| `GET` | `/api/v1/jobs/health` | Inspect queue depths, active workers, stuck jobs | `jobs.read` |

---

## 🤖 Enterprise Agent Runtime & Typed Tool Orchestration (Task 24)

> Controlled enterprise multi-step agent runtime with deterministic planning, server-enforced tool authorization, bounded multi-dimensional budgets, operator approval gates, and crash-resilient checkpointing.

### 1. Architecture Highlights
- **Deterministic Pipeline**: `Policy` $\to$ `Plan` $\to$ `Typed Tool Calls` $\to$ `Validation` $\to$ `Execution` $\to$ `Evidence` $\to$ `Checkpoint` $\to$ `Final Answer`.
- **The LLM is NOT the Security Boundary**: Server-side validation of Pydantic schemas (`extra="forbid"`), role-based access controls (RBAC), agent profile allowlists, and strict tenant isolation.
- **Strictly Bounded Runtime**: Hard finite bounds on step counts (`max_steps`), token consumption, dollar cost (`max_cost_usd`), and wall-clock execution time.
- **Prohibited Capabilities**: Zero shell execution, arbitrary Python `eval`, direct raw SQL queries bypassing Task 17 guardrails, web searching, or browser automation.
- **Typed Tool Registry**: Typed adapters wrapping domain services (`analyst.query`, `sql.query`, `rag.retrieve`, `report.create`, `evaluation.run`).
- **Human-in-the-Loop Approval Gates**: Sensitive tools (such as `report.create`) trigger approval gates, pausing execution until reviewed and resolved by an operator.
- **Immutable Checkpoints & Recovery**: Checkpoints taken after every step enable crash recovery, resumption, and idempotent tool deduplication.
- **Grounding & Provenance**: Strict *No Evidence $\to$ No Claim* verification ensuring assertions are backed by concrete evidence items.

### 2. API Endpoints
| Method | Endpoint | Description | Required Permission |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/agents/sessions` | Create an agent session with a validated execution plan | `agents.create` |
| `GET` | `/api/v1/agents/sessions/{id}` | Get session status, current step, final answer, usage | `agents.read` |
| `GET` | `/api/v1/agents/sessions/{id}/plan` | Retrieve structured execution plan and estimated bounds | `agents.read` |
| `GET` | `/api/v1/agents/sessions/{id}/steps` | List executed steps, evidence items, and step durations | `agents.read` |
| `POST` | `/api/v1/agents/sessions/{id}/start` | Execute or dispatch session run synchronously/asynchronously | `agents.execute` |
| `POST` | `/api/v1/agents/sessions/{id}/cancel` | Cancel an active or pending agent session | `agents.cancel` |
| `POST` | `/api/v1/agents/sessions/{id}/resume` | Resume paused or awaiting_approval session from checkpoint | `agents.resume` |
| `GET` | `/api/v1/agents/sessions/{id}/approvals` | List approval gate requests for a session | `agents.read` |
| `POST` | `/api/v1/agents/sessions/{id}/approvals/{aid}/approve` | Authorize sensitive tool execution step | `agents.approve` |
| `POST` | `/api/v1/agents/sessions/{id}/approvals/{aid}/reject` | Reject sensitive tool execution step | `agents.approve` |

---

## 🧠 Enterprise Agent Memory & Stateful Context Architecture (Task 25)

Task 25 establishes a bounded, tenant-scoped, permission-aware memory layer for the Agent Runtime across 4 tiers:
- **Short-Term**: Transient session variables, prompt context, and recent dialog messages (TTL: 1 hour).
- **Working Memory**: Active task entities, intermediate evidence references, and constraints (TTL: 24 hours).
- **Episodic Memory**: Grounded historical outcomes and successful analytic workflows (TTL: 30 days).
- **Semantic Memory**: Persistent, verified organizational knowledge and user preferences (Indefinite).

### Key Architectural Guardrails
* **Memory ≠ Dump of All Conversations**: Candidates are extracted, validated, filtered for credentials, deduplicated via canonical SHA-256 hashes, and bounded by token budgets (`MAX_MEMORY_CONTEXT_TOKENS`).
* **The LLM is NOT the Security Boundary**: Server-side RBAC (`memory.read`, `memory.create`, `memory.update`, `memory.delete`, `memory.admin`) and relational foreign key constraints govern all access.
* **Privacy & Secret Redaction**: The `MemoryPrivacyFilter` prevents storage of API keys, JWTs, passwords, private keys, or DB credentials.
* **Prompt Injection Neutralization**: Injected context is strictly wrapped in `<untrusted_memory>` blocks with system instructions treating memory as passive contextual data rather than executable directives.
* **Dual Persistence Model**: PostgreSQL serves as canonical metadata and immutable version history (`memory_versions`); Qdrant provides dense vector search with mandatory tenant filters.

### Memory REST API Endpoints

| Method | Endpoint | Description | Required Permission |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/memory` | Create or declare a memory item | `memory.create` |
| `GET` | `/api/v1/memory` | List paginated tenant memory items | `memory.read` |
| `GET` | `/api/v1/memory/{id}` | Get memory item details by ID | `memory.read` |
| `PATCH`| `/api/v1/memory/{id}` | Update memory content (spawns new version) | `memory.update` |
| `DELETE`| `/api/v1/memory/{id}`| Soft-delete memory item & evict vector | `memory.delete` |
| `POST` | `/api/v1/memory/search` | Semantic and metadata hybrid search | `memory.read` |
| `GET` | `/api/v1/memory/summary` | Summary counts by tier, status, and privacy | `memory.read` |

---

## 🧪 Quality & Testing Commands

Run the unit test suite:
```bash
pytest tests/unit/
```

Run document parsing unit tests:
```bash
pytest tests/unit/test_parsers.py tests/unit/test_ingestion_limits.py
```

Run ingestion integration tests against real PostgreSQL:
```bash
pytest tests/integration/test_ingestion_pipeline.py
```

Run full test suite:
```bash
pytest
```

Run linter and formatting checks:
```bash
ruff check .
ruff format --check .
```

Run static type checking with MyPy:
```bash
mypy app tests
```

Verify syntax compilation:
```bash
python -m compileall app
```


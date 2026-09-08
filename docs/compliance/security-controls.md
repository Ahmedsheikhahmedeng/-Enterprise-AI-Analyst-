# Security Controls Catalog & Baseline Requirements

> [!NOTE]
> **Explicit Certification Boundary**: This implementation provides technical control readiness and evidence management. It does not constitute SOC 2, ISO 27001, GDPR, HIPAA, or any other formal certification.

---

## 1. Baseline Technical Controls

The platform implements 24 canonical security controls spanning 9 core technical categories:

### Identity & Authentication
- **`SEC-AUTH-001`**: Password Hashing & Strength Policy (Argon2id, minimum 12 chars, entropy validation)
- **`SEC-AUTH-002`**: Token Expiry, Rotation & Revocation (Strict short-lived JWTs, sliding refresh rotation, replay detection)

### Authorization & RBAC
- **`SEC-RBAC-001`**: Role-Based Access Control Enforcement (Strict permission verification on all protected endpoints)
- **`SEC-RBAC-002`**: Tenant Context Boundary (Every request must resolve to an authenticated, verified tenant context)

### Tenant Isolation
- **`SEC-TENANT-001`**: Cross-Tenant Read Prevention (SQL / Vector / Storage queries partitioned by `organization_id`)
- **`SEC-TENANT-002`**: Cross-Tenant Write & Mutation Prevention (Tenant-scoped updates and deletes)

### Secrets Management
- **`SEC-SECRET-001`**: Secret Redaction in Telemetry & Logs (Automated masking of API keys, tokens, and credentials)
- **`SEC-SECRET-002`**: Rejection of Default / Weak Secrets (Startup validation preventing hardcoded secret patterns)

### Network Security
- **`SEC-NET-001`**: Server-Side Request Forgery (SSRF) Defense (Private IP, loopback, and metadata endpoint blocking)
- **`SEC-NET-002`**: Restricted Outbound Destination Routing (Strict egress domain and connector whitelisting)

### Data Protection
- **`SEC-DATA-001`**: Upload Validation & Object Key Traversal Protection (MIME check, magic bytes, sanitization)
- **`SEC-DATA-002`**: CSV Formula Injection Defense (Sanitization of spreadsheet cells starting with `=`, `+`, `-`, `@`)

### Audit & Traceability
- **`SEC-LOG-001`**: Comprehensive Security & Mutation Audit Logging (Structured JSON with actor, timestamp, tenant)
- **`SEC-LOG-002`**: Distributed Trace Correlation (Every request tracked with `trace_id`, `span_id`, and `request_id`)

### AI Safety & Governance
- **`SEC-AI-001`**: Prompt Injection Defense (Deterministic heuristic & semantic filtering against jailbreak attempts)
- **`SEC-AI-002`**: Untrusted Document Isolation (Delimited sandboxing of user uploads before LLM ingestion)
- **`SEC-AI-003`**: Output Grounding & Verification (Deterministic verification of generated SQL queries and citations)

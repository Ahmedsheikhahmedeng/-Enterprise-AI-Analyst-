# Security Architecture & Trust Boundaries

## 1. Architectural Philosophy

Security in the Enterprise AI Analyst platform is built around **Defense in Depth** and **Zero Trust Isolation**:
- No entity (user, tenant, document, external payload) is implicitly trusted.
- Security controls are centralized in `app/security/` rather than scattered ad-hoc.
- Every layer enforces explicit boundaries:
  - Transport (TLS, Security Headers, CORS)
  - Identity (JWT, Argon2id, Refresh Token Families)
  - Tenancy (Immutable TenantContext, IDOR assertions)
  - Compute & Storage (AST-based read-only SQL, Magic-byte validated uploads)
  - Generative AI (Prompt injection classification, SSRF protection, Formula injection neutralization)

---

## 2. Core Security Components (`app/security/`)

```
app/security/
├── config.py              # SecurityConfig with limits, timeouts, and allowlists
├── exceptions.py          # Domain security exceptions
├── policies.py            # TenantSecurityPolicy and IDOR assertion helpers
├── context.py             # Security ContextVar propagation
├── headers.py             # SecurityHeadersMiddleware (CSP, HSTS, nosniff, DENY)
├── cors.py                # Hardened CORS policy
├── rate_limit.py          # Redis-backed RateLimiter with in-memory fallback
├── replay.py              # Idempotency-Key replay protection
├── secrets.py             # SecretSafeLogger and credential redaction
├── sanitization.py        # Output escaping, Unicode normalization, CRLF protection
├── input_validation.py    # SecurityInputValidator (path traversal, control chars)
├── prompt_injection.py    # PromptInjectionDetector (multi-tier classification)
├── ssrf.py                # SSRFProtection (private CIDR and metadata blocking)
├── file_security.py       # File upload validation (magic bytes, MIME, extensions)
├── export_security.py     # CSV formula injection protection, safe filenames
├── audit.py               # Standard security event audit logging
├── threat_model.py        # Programmatic threat model definitions
└── service.py             # Central SecurityService facade
```

---

## 3. Data Flow & Boundary Enforcement

1. **Incoming Request**:
   - `SecurityHeadersMiddleware`: Injects standard headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Content-Security-Policy: default-src 'none'`).
   - `ObservabilityMiddleware`: Attaches correlation IDs and binds trace context.
   - `RateLimiter`: Enforces per-endpoint tiered quotas (Login, Register, Analyst, Upload, Export).
   - `IdempotencyValidator`: Evaluates `Idempotency-Key` headers for mutating operations.

2. **Authentication & Authorization**:
   - JWT decoding enforces algorithm allowlist (`HS256`), issuer, audience, expiration, and clock skew tolerance.
   - Rejects `alg=none`, expired tokens, or tokens with mismatched types.
   - `TenantSecurityPolicy` validates tenant membership and locks resource operations to `tenant.organization_id`.

3. **Untrusted Data Boundary**:
   - Chunks retrieved from documents and user queries are treated strictly as **Untrusted Data**.
   - Input texts pass through `PromptInjectionDetector` to screen for adversarial prompt overrides.
   - SQL generation is constrained by AST validation (`sqlglot`), prohibiting non-SELECT queries, system schemas, and dangerous functions.

4. **Outputs & Exports**:
   - CSV and spreadsheet outputs pass through `sanitize_csv_cell` to neutralize formula injection (`=`, `+`, `-`, `@`).
   - Export filenames are sanitized to prevent directory traversal (`..`, null bytes, slashes).

# Security Controls Matrix

This document maps all implemented security controls to specific threats, architectural components, and automated test coverage.

| Control Identifier | Threat Addressed | Implementation Module | Automated Test File | Status |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-AUTH-01** | JWT Signature Forgery (`alg=none`) | `app.auth.jwt`, `app.security.config` | `tests/security/test_auth_security.py` | **IMPLEMENTED** |
| **SEC-AUTH-02** | Token Lifetime / Clock Skew | `app.auth.jwt`, `app.security.config` | `tests/security/test_auth_security.py` | **IMPLEMENTED** |
| **SEC-AUTH-03** | Refresh Token Reuse Hijack | `app.auth.service` | `tests/security/test_auth_security.py` | **IMPLEMENTED** |
| **SEC-TENANT-01** | Cross-Tenant Data Access (IDOR) | `app.security.policies.TenantSecurityPolicy` | `tests/security/test_tenant_isolation_security.py` | **IMPLEMENTED** |
| **SEC-TENANT-02** | Nested Resource Hijacking | `app.security.policies.TenantSecurityPolicy` | `tests/security/test_tenant_isolation_security.py` | **IMPLEMENTED** |
| **SEC-AI-01** | Prompt Injection (System Prompt Leak) | `app.security.prompt_injection.PromptInjectionDetector` | `tests/security/test_prompt_injection.py` | **IMPLEMENTED** |
| **SEC-AI-02** | Unicode Obfuscation / Confusables | `app.security.sanitization`, `PromptInjectionDetector` | `tests/security/test_prompt_injection.py` | **IMPLEMENTED** |
| **SEC-SQL-01** | SQL AST Write / DDL / Side-Effects | `app.sql_agent.validator.SQLSecurityValidator` | `tests/security/test_sql_security.py` | **IMPLEMENTED** |
| **SEC-SQL-02** | SQL Resource Abuse (Cartesian Join) | `app.security.policies`, `SQLSecurityValidator` | `tests/security/test_sql_security.py` | **IMPLEMENTED** |
| **SEC-FILE-01** | File Magic Byte Spoofing | `app.security.file_security.FileSecurityValidator` | `tests/security/test_file_security.py` | **IMPLEMENTED** |
| **SEC-FILE-02** | Upload Path Traversal | `app.security.file_security.FileSecurityValidator` | `tests/security/test_file_security.py` | **IMPLEMENTED** |
| **SEC-EXP-01** | CSV / Spreadsheet Formula Injection | `app.security.export_security.sanitize_csv_cell` | `tests/security/test_exports_security.py` | **IMPLEMENTED** |
| **SEC-EXP-02** | Export Path Traversal in Filenames | `app.security.export_security.sanitize_export_filename` | `tests/security/test_exports_security.py` | **IMPLEMENTED** |
| **SEC-NET-01** | SSRF to Localhost & Private Networks | `app.security.ssrf.SSRFProtection` | `tests/security/test_ssrf.py` | **IMPLEMENTED** |
| **SEC-NET-02** | SSRF to Cloud Metadata Service | `app.security.ssrf.SSRFProtection` | `tests/security/test_ssrf.py` | **IMPLEMENTED** |
| **SEC-NET-03** | Redirect Chain SSRF Bypass | `app.security.ssrf.SSRFProtection` | `tests/security/test_ssrf.py` | **IMPLEMENTED** |
| **SEC-RATE-01** | Endpoint Brute Force & Denial of Service | `app.security.rate_limit.RateLimiter` | `tests/security/test_rate_limiting.py` | **IMPLEMENTED** |
| **SEC-REP-01** | State Mutation Replay (`Idempotency-Key`) | `app.security.replay.IdempotencyManager` | `tests/security/test_replay.py` | **IMPLEMENTED** |
| **SEC-HTTP-01** | Missing Security Headers (MIME/Clickjack) | `app.security.headers.SecurityHeadersMiddleware` | `tests/security/test_headers.py` | **IMPLEMENTED** |
| **SEC-CORS-01** | CORS Credential Exposure via Wildcard | `app.security.cors.get_cors_config` | `tests/security/test_headers.py` | **IMPLEMENTED** |
| **SEC-DATA-01** | Credential Leakage in Telemetry & Logs | `app.security.secrets.SecretSafeLogger` | `tests/security/test_secrets.py` | **IMPLEMENTED** |
| **SEC-AUDIT-01**| Unaudited Security Violations | `app.security.audit.record_security_audit_event` | `tests/security/test_regression_security.py` | **IMPLEMENTED** |

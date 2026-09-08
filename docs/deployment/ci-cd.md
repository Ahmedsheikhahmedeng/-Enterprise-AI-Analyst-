# Continuous Integration & Deployment (CI/CD)

## 1. Pipeline Overview
The CI/CD workflow guarantees that code is tested, validated, scanned, and verified before any deployment reaches production.

```text
PR Created / Main Push
           ↓
┌──────────────────────────────────────────────┐
│ CI Pipeline (.github/workflows/ci.yml)       │
│  - Backend: Ruff, MyPy, Compile, Alembic,    │
│             Pytest Unit & Integration        │
│  - Frontend: npm ci, ESLint, TypeScript,     │
│              Vitest, Next.js Build           │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ Security Scanning (.github/workflows/sec.yml)│
│  - Gitleaks Secret Scanner                   │
│  - Bandit SAST Static Analysis               │
│  - pip-audit & npm audit Dependency Scans    │
│  - Trivy Container Image Scan                │
└──────────────────────┬───────────────────────┘
                       │
                       ▼ (On Tag v*.*.*)
┌──────────────────────────────────────────────┐
│ Release Pipeline (.github/workflows/rel.yml) │
│  - Build Immutable Images (Git SHA, Version) │
│  - Generate CycloneDX SBOM                   │
│  - TASK 33 Quality Gate Check (BLOCK_RELEASE)│
│  - Human Deployment Approval Gate            │
│  - Decoupled DB Migration (migrate.sh)       │
│  - Container Rollout                         │
│  - Smoke Tests & Release Manifest Artifact   │
└──────────────────────────────────────────────┘
```

## 2. Release Quality Gates
Deployments are blocked automatically if:
- Any unit, integration, or contract test fails.
- Alembic detects untracked database drift (`alembic check`).
- Gitleaks detects committed credentials or tokens.
- TASK 33 Continuous Evaluation returns a `BLOCK_RELEASE` decision.
- Production deployment is missing human reviewer approval.

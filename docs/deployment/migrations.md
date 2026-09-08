# Database Migration Strategy & Safety Runbook

## 1. Golden Rules
1. **Decoupled Execution**: Migrations are never executed automatically inside application containers during startup. They are executed via a dedicated release step (`infra/scripts/migrate.sh`).
2. **Backward Compatibility**: All schema changes must follow expand-and-contract patterns to allow old and new application versions to coexist during deployment rollout.
3. **No Automatic Destructive Downgrades**: If a migration fails, the deployment halts immediately. Automated downgrades are prohibited to prevent catastrophic data loss.

## 2. Running Migrations Manually
```bash
export DATABASE_URL="postgresql+asyncpg://analyst_prod_user:password@localhost:5432/enterprise_ai_analyst"
bash infra/scripts/migrate.sh
```

## 3. Pre-Migration Safety Checks
Before applying migrations to production, verify consistency:
```bash
cd backend
python -m alembic check
python -m alembic history
```

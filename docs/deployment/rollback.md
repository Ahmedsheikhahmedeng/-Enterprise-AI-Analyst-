# Production Rollback Runbook

## 1. Application Rollback
If a newly deployed release experiences unexpected application errors or crashes, roll back the container images to the previous known-good image tag:

```bash
# Rollback application containers to previous release tag (e.g. v0.1.0)
bash infra/scripts/rollback.sh v0.1.0
```

This immediately updates the running Backend, Worker, and Frontend containers without altering the database schema.

## 2. Database Rollback (Explicit Only)
Database schema downgrades are dangerous and should be avoided whenever possible. If an explicit downgrade is strictly necessary and vetted:

```bash
# Explicit database downgrade with target Alembic revision
bash infra/scripts/rollback.sh v0.1.0 --with-db-downgrade <target_revision>
```
The script will prompt for interactive confirmation or require `FORCE_ROLLBACK=true`.

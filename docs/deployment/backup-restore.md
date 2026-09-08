# Database Backup & Restoration Runbook

## 1. Automated Backups
Automated database backups are created using `infra/scripts/backup.sh`:
- Compressed with `gzip -9`.
- Accompanied by a `.sha256` integrity hash.
- Pruned according to retention policy (default: 14 days).

```bash
# Execute manual backup
BACKUP_DIR="/var/backups/analyst" bash infra/scripts/backup.sh
```

## 2. Restoration & Integrity Testing
Restoration requires the backup archive and verifies the SHA256 checksum prior to execution:

```bash
# Verify and restore into an isolated staging/verification database
bash infra/scripts/restore.sh /var/backups/analyst/analyst_db_backup_20260907.sql.gz enterprise_ai_analyst_staging
```

## 3. Disaster Recovery Objectives & Clarifications

> [!IMPORTANT]
> **Operational Planning Targets vs. Demonstrated Capabilities**:
> - **Target RTO (Recovery Time Objective): 1 hour** — Documented architectural target for restoring core services from cold standby archives.
> - **Target RPO (Recovery Point Objective): 15 minutes** — Documented architectural SLA target.
> 
> *Capability Clarification*:
> The baseline script `infra/scripts/backup.sh` provides periodic cold snapshot dumps via `pg_dump`. 
> Achieving the 15-minute RPO target in production environments requires continuous Write-Ahead Log (WAL) archiving and Point-in-Time Recovery (PITR) infrastructure (e.g. AWS RDS automated continuous backups, PostgreSQL `archive_command` with WAL-G, or pgBackRest). Without continuous WAL archiving enabled, the effective RPO is bounded by the cron frequency of snapshot execution (e.g., daily or hourly).

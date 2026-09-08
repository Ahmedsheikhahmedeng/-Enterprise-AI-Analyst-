# Diagnostic Runbooks & Safety Governance

## 1. Principles & Safety Constraints

Runbooks in the Enterprise SRE layer serve as **guided diagnostic procedures and safe mitigation playbooks**. They are strictly governed by safety validation policies:

* **Read-Only / Diagnostic by Design**: Runbooks provide verified read-only inspection commands and approved non-destructive actions.
* **Prohibition of Destructive Commands**: The SRE engine programmatically scans all runbook steps upon submission and rejects steps containing:
  - `rm -rf`
  - `DROP TABLE` or `DROP DATABASE`
  - `TRUNCATE`
  - `kill -9`
  - Unbounded `DELETE FROM` statements
* **No Arbitrary Code Execution**: Runbooks do not execute arbitrary shell or Python scripts autonomously on production hosts.

---

## 2. Versioning & Immutability

* **Draft Mode**: Runbooks are initially created as drafts (`is_published: false`) and can be edited and validated.
* **Published Immutability**: Once published (`is_published: true`), in-place mutation of the existing record is prohibited.
* **Revisioning**: Updates to a published runbook require incrementing the version number or creating a new revision.

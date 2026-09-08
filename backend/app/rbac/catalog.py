"""Centralized RBAC Permission Catalog, System Roles, and Default Role Mappings."""

from typing import Final

# ---------------------------------------------------------------------------
# Granular Permission Identifiers
# ---------------------------------------------------------------------------

# Users
PERM_USERS_READ: Final[str] = "users.read"
PERM_USERS_MANAGE: Final[str] = "users.manage"
PERM_USERS_INVITE: Final[str] = "users.invite"
PERM_USERS_REMOVE: Final[str] = "users.remove"

# Organization
PERM_ORGANIZATION_READ: Final[str] = "organization.read"
PERM_ORGANIZATION_MANAGE: Final[str] = "organization.manage"

# Documents
PERM_DOCUMENTS_READ: Final[str] = "documents.read"
PERM_DOCUMENTS_WRITE: Final[str] = "documents.write"
PERM_DOCUMENTS_DELETE: Final[str] = "documents.delete"
PERM_DOCUMENTS_MANAGE: Final[str] = "documents.manage"

# Datasets (Legacy)
PERM_DATASETS_READ: Final[str] = "datasets.read"
PERM_DATASETS_WRITE: Final[str] = "datasets.write"
PERM_DATASETS_DELETE: Final[str] = "datasets.delete"

# Datasets & Materialization (TASK 27)
PERM_DATASET_READ: Final[str] = "dataset.read"
PERM_DATASET_CREATE: Final[str] = "dataset.create"
PERM_DATASET_UPDATE: Final[str] = "dataset.update"
PERM_DATASET_DELETE: Final[str] = "dataset.delete"
PERM_DATASET_INGEST: Final[str] = "dataset.ingest"
PERM_DATASET_PROFILE: Final[str] = "dataset.profile"
PERM_DATASET_VERSIONS: Final[str] = "dataset.versions"

# Data Sources
PERM_DATA_SOURCES_READ: Final[str] = "data_sources.read"
PERM_DATA_SOURCES_WRITE: Final[str] = "data_sources.write"
PERM_DATA_SOURCES_DELETE: Final[str] = "data_sources.delete"

# Connectors & Data Sources (TASK 26)
PERM_DATASOURCE_READ: Final[str] = "datasource.read"
PERM_DATASOURCE_CREATE: Final[str] = "datasource.create"
PERM_DATASOURCE_UPDATE: Final[str] = "datasource.update"
PERM_DATASOURCE_DELETE: Final[str] = "datasource.delete"
PERM_DATASOURCE_TEST: Final[str] = "datasource.test"
PERM_DATASOURCE_QUERY: Final[str] = "datasource.query"
PERM_DATASOURCE_SYNC: Final[str] = "datasource.sync"
PERM_DATASOURCE_SCHEMA: Final[str] = "datasource.schema"

# Reports
PERM_REPORTS_READ: Final[str] = "reports.read"
PERM_REPORTS_CREATE: Final[str] = "reports.create"
PERM_REPORTS_UPDATE: Final[str] = "reports.update"
PERM_REPORTS_DELETE: Final[str] = "reports.delete"
PERM_REPORTS_PUBLISH: Final[str] = "reports.publish"
PERM_REPORTS_EXPORT: Final[str] = "reports.export"
PERM_REPORTS_ARCHIVE: Final[str] = "reports.archive"

# Analytics
PERM_ANALYTICS_READ: Final[str] = "analytics.read"
PERM_ANALYTICS_EXECUTE: Final[str] = "analytics.execute"

# AI
PERM_AI_CHAT: Final[str] = "ai.chat"
PERM_AI_ANALYZE: Final[str] = "ai.analyze"

# Audit & Usage
PERM_AUDIT_READ: Final[str] = "audit.read"
PERM_USAGE_READ: Final[str] = "usage.read"

# Evaluation (TASK 20 & TASK 33)
PERM_EVALUATION_READ: Final[str] = "evaluation.read"
PERM_EVALUATION_CREATE: Final[str] = "evaluation.create"
PERM_EVALUATION_RUN: Final[str] = "evaluation.run"
PERM_EVALUATION_COMPARE: Final[str] = "evaluation.compare"
PERM_EVALUATION_MONITOR_READ: Final[str] = "evaluation.monitor.read"
PERM_EVALUATION_BENCHMARK_MANAGE: Final[str] = "evaluation.benchmark.manage"
PERM_EVALUATION_RUN_EXECUTE: Final[str] = "evaluation.run.execute"
PERM_EVALUATION_QUALITY_GATE_READ: Final[str] = "evaluation.quality_gate.read"
PERM_EVALUATION_RELEASE_APPROVE: Final[str] = "evaluation.release.approve"
PERM_EVALUATION_HUMAN_REVIEW: Final[str] = "evaluation.human_review"

# Observability
PERM_OBSERVABILITY_READ: Final[str] = "observability.read"
PERM_OBSERVABILITY_METRICS: Final[str] = "observability.metrics"
PERM_OBSERVABILITY_HEALTH: Final[str] = "observability.health"

# Background Jobs
PERM_JOBS_READ: Final[str] = "jobs.read"
PERM_JOBS_CREATE: Final[str] = "jobs.create"
PERM_JOBS_CANCEL: Final[str] = "jobs.cancel"
PERM_JOBS_RETRY: Final[str] = "jobs.retry"
PERM_JOBS_ADMIN: Final[str] = "jobs.admin"

# Agents
PERM_AGENTS_READ: Final[str] = "agents.read"
PERM_AGENTS_CREATE: Final[str] = "agents.create"
PERM_AGENTS_EXECUTE: Final[str] = "agents.execute"
PERM_AGENTS_CANCEL: Final[str] = "agents.cancel"
PERM_AGENTS_APPROVE: Final[str] = "agents.approve"
PERM_AGENTS_RESUME: Final[str] = "agents.resume"

# Memory
PERM_MEMORY_READ: Final[str] = "memory.read"
PERM_MEMORY_CREATE: Final[str] = "memory.create"
PERM_MEMORY_UPDATE: Final[str] = "memory.update"
PERM_MEMORY_DELETE: Final[str] = "memory.delete"
PERM_MEMORY_ADMIN: Final[str] = "memory.admin"

# Semantic Catalog & Layer (TASK 28)
PERM_SEMANTIC_READ: Final[str] = "semantic.read"
PERM_SEMANTIC_CREATE: Final[str] = "semantic.create"
PERM_SEMANTIC_UPDATE: Final[str] = "semantic.update"
PERM_SEMANTIC_DELETE: Final[str] = "semantic.delete"
PERM_SEMANTIC_VERIFY: Final[str] = "semantic.verify"
PERM_SEMANTIC_PUBLISH: Final[str] = "semantic.publish"

# Knowledge Graph & Relationship Reasoning (TASK 29)
PERM_GRAPH_READ: Final[str] = "graph.read"
PERM_GRAPH_CREATE: Final[str] = "graph.create"
PERM_GRAPH_UPDATE: Final[str] = "graph.update"
PERM_GRAPH_DELETE: Final[str] = "graph.delete"
PERM_GRAPH_TRAVERSE: Final[str] = "graph.traverse"
PERM_GRAPH_PUBLISH: Final[str] = "graph.publish"

# LLM Gateway & AI Provider Management (TASK 30)
PERM_LLM_READ: Final[str] = "llm.read"
PERM_LLM_MANAGE: Final[str] = "llm.manage"
PERM_LLM_POLICY_READ: Final[str] = "llm.policy.read"
PERM_LLM_POLICY_UPDATE: Final[str] = "llm.policy.update"
PERM_LLM_MODEL_APPROVE: Final[str] = "llm.model.approve"
PERM_LLM_MODEL_DISABLE: Final[str] = "llm.model.disable"
PERM_LLM_USAGE_READ: Final[str] = "llm.usage.read"

# Enterprise AI Response & Decision Orchestration (TASK 31)
PERM_ORCHESTRATION_EXECUTE: Final[str] = "orchestration.execute"
PERM_ORCHESTRATION_READ: Final[str] = "orchestration.read"
PERM_ORCHESTRATION_MANAGE: Final[str] = "orchestration.manage"

# Governance & Human-in-the-Loop Workflow (TASK 32)
PERM_GOVERNANCE_READ: Final[str] = "governance.read"
PERM_GOVERNANCE_CREATE: Final[str] = "governance.create"
PERM_GOVERNANCE_REVIEW: Final[str] = "governance.review"
PERM_GOVERNANCE_APPROVE: Final[str] = "governance.approve"
PERM_GOVERNANCE_REJECT: Final[str] = "governance.reject"
PERM_GOVERNANCE_MANAGE_POLICY: Final[str] = "governance.manage_policy"
PERM_GOVERNANCE_VIEW_AUDIT: Final[str] = "governance.view_audit"

# Site Reliability Engineering & Operations (TASK 37)
PERM_SRE_ALERT_READ: Final[str] = "sre.alert.read"
PERM_SRE_ALERT_MANAGE: Final[str] = "sre.alert.manage"
PERM_SRE_INCIDENT_READ: Final[str] = "sre.incident.read"
PERM_SRE_INCIDENT_MANAGE: Final[str] = "sre.incident.manage"
PERM_SRE_RUNBOOK_READ: Final[str] = "sre.runbook.read"
PERM_SRE_RUNBOOK_MANAGE: Final[str] = "sre.runbook.manage"
PERM_SRE_SLO_READ: Final[str] = "sre.slo.read"
PERM_SRE_SLO_MANAGE: Final[str] = "sre.slo.manage"
PERM_SRE_MAINTENANCE_MANAGE: Final[str] = "sre.maintenance.manage"
PERM_SRE_RELEASE_GATE_READ: Final[str] = "sre.release_gate.read"

# Reliability & Chaos Validation (TASK 38)
PERM_RELIABILITY_READ: Final[str] = "reliability.read"
PERM_RELIABILITY_RUN: Final[str] = "reliability.run"
PERM_RELIABILITY_MANAGE: Final[str] = "reliability.manage"
PERM_RELIABILITY_READINESS: Final[str] = "reliability.readiness"

# Enterprise Security & Compliance Governance (TASK 39)
PERM_COMPLIANCE_READ: Final[str] = "compliance.read"
PERM_COMPLIANCE_ASSESS: Final[str] = "compliance.assess"
PERM_COMPLIANCE_MANAGE: Final[str] = "compliance.manage"
PERM_COMPLIANCE_EVIDENCE_READ: Final[str] = "compliance.evidence.read"
PERM_COMPLIANCE_EVIDENCE_MANAGE: Final[str] = "compliance.evidence.manage"
PERM_COMPLIANCE_FINDINGS_READ: Final[str] = "compliance.findings.read"
PERM_COMPLIANCE_FINDINGS_MANAGE: Final[str] = "compliance.findings.manage"
PERM_COMPLIANCE_ACCESS_REVIEW: Final[str] = "compliance.access_review"
PERM_COMPLIANCE_RETENTION_MANAGE: Final[str] = "compliance.retention.manage"
PERM_COMPLIANCE_PRIVACY_MANAGE: Final[str] = "compliance.privacy.manage"
PERM_COMPLIANCE_RISK_ACCEPTANCE: Final[str] = "compliance.risk_acceptance"
PERM_COMPLIANCE_SECURITY_ADMIN: Final[str] = "compliance.security_admin"

# Enterprise FinOps, AI Cost Governance & Usage Optimization (TASK 40)
PERM_FINOPS_READ: Final[str] = "finops.read"
PERM_FINOPS_MANAGE: Final[str] = "finops.manage"
PERM_FINOPS_BUDGET_READ: Final[str] = "finops.budget.read"
PERM_FINOPS_BUDGET_MANAGE: Final[str] = "finops.budget.manage"
PERM_FINOPS_QUOTA_MANAGE: Final[str] = "finops.quota.manage"
PERM_FINOPS_PRICING_MANAGE: Final[str] = "finops.pricing.manage"
PERM_FINOPS_ANOMALY_READ: Final[str] = "finops.anomaly.read"
PERM_FINOPS_POLICY_MANAGE: Final[str] = "finops.policy.manage"
PERM_FINOPS_RECONCILIATION_READ: Final[str] = "finops.reconciliation.read"
PERM_FINOPS_OPTIMIZATION_READ: Final[str] = "finops.optimization.read"

# ---------------------------------------------------------------------------
# Complete Permission Catalog Specification
# ---------------------------------------------------------------------------


SYSTEM_PERMISSIONS: Final[dict[str, str]] = {
    # Users
    PERM_USERS_READ: "Read user profiles and membership lists",
    PERM_USERS_MANAGE: "Manage user roles and administrative properties",
    PERM_USERS_INVITE: "Invite new users into an organization",
    PERM_USERS_REMOVE: "Remove users from an organization",
    # Organization
    PERM_ORGANIZATION_READ: "View organization details and configuration",
    PERM_ORGANIZATION_MANAGE: "Modify organization settings and metadata",
    # Documents
    PERM_DOCUMENTS_READ: "Read and download documents",
    PERM_DOCUMENTS_WRITE: "Upload and update documents",
    PERM_DOCUMENTS_DELETE: "Delete documents from organization",
    PERM_DOCUMENTS_MANAGE: "Configure document partitions and processing pipelines",
    # Datasets
    PERM_DATASETS_READ: "View dataset structures and data records",
    PERM_DATASETS_WRITE: "Create and update datasets and schemas",
    PERM_DATASETS_DELETE: "Delete datasets and data columns",
    PERM_DATASET_READ: "Read dataset metadata, profile, and schemas",
    PERM_DATASET_CREATE: "Create new datasets for materialization",
    PERM_DATASET_UPDATE: "Update dataset metadata, classification, or settings",
    PERM_DATASET_DELETE: "Delete or archive datasets",
    PERM_DATASET_INGEST: "Trigger materialization and ingestion pipeline for datasets",
    PERM_DATASET_PROFILE: "Inspect statistical profiling of datasets",
    PERM_DATASET_VERSIONS: "List and inspect historical dataset versions",
    # Data Sources
    PERM_DATA_SOURCES_READ: "View external data source connections",
    PERM_DATA_SOURCES_WRITE: "Configure and update data source connections",
    PERM_DATA_SOURCES_DELETE: "Remove external data sources",
    PERM_DATASOURCE_READ: "View external data source connections and schema",
    PERM_DATASOURCE_CREATE: "Register new external data source connectors",
    PERM_DATASOURCE_UPDATE: "Update data source connector configuration and status",
    PERM_DATASOURCE_DELETE: "Delete data source connections",
    PERM_DATASOURCE_TEST: "Test live connectivity to external data source",
    PERM_DATASOURCE_QUERY: "Execute analytical queries against external data source",
    PERM_DATASOURCE_SYNC: "Trigger background synchronization of data sources",
    PERM_DATASOURCE_SCHEMA: "Discover or refresh data source schema",
    # Reports
    PERM_REPORTS_READ: "View generated enterprise reports",
    PERM_REPORTS_CREATE: "Generate new analytical reports",
    PERM_REPORTS_UPDATE: "Edit existing reports and notes",
    PERM_REPORTS_DELETE: "Delete analytical reports",
    PERM_REPORTS_PUBLISH: "Publish reports as immutable versions",
    PERM_REPORTS_EXPORT: "Export reports to PDF, CSV, Markdown, and HTML formats",
    PERM_REPORTS_ARCHIVE: "Archive historical reports",
    # Analytics
    PERM_ANALYTICS_READ: "View analytics runs and dashboards",
    PERM_ANALYTICS_EXECUTE: "Execute analytical queries and calculations",
    # AI
    PERM_AI_CHAT: "Participate in AI conversations and queries",
    PERM_AI_ANALYZE: "Execute automated AI analytical deep dives",
    # Audit & Usage
    PERM_AUDIT_READ: "Inspect organization audit trails",
    PERM_USAGE_READ: "Inspect platform consumption and token usage",
    # Evaluation (TASK 20 & TASK 33)
    PERM_EVALUATION_READ: "View evaluation datasets, benchmark runs, and scorecards",
    PERM_EVALUATION_CREATE: "Create and manage evaluation datasets and test cases",
    PERM_EVALUATION_RUN: "Execute benchmark evaluation runs on datasets",
    PERM_EVALUATION_COMPARE: "Compare benchmark runs and perform regression analysis",
    PERM_EVALUATION_MONITOR_READ: "Read continuous quality monitoring analytics, sampling metrics, and calibration",
    PERM_EVALUATION_BENCHMARK_MANAGE: "Create, update, and manage versioned benchmarks and evaluation suites",
    PERM_EVALUATION_RUN_EXECUTE: "Execute continuous evaluation suites, model comparisons, and calibration runs",
    PERM_EVALUATION_QUALITY_GATE_READ: "Inspect quality gate policies, violation details, and release readiness reports",
    PERM_EVALUATION_RELEASE_APPROVE: "Approve deployment releases when gated by quality policies",
    PERM_EVALUATION_HUMAN_REVIEW: "Submit human evaluation scores and qualitative reviews",
    # Observability
    PERM_OBSERVABILITY_READ: "Inspect system operational telemetry, traces, and SLO statuses",
    PERM_OBSERVABILITY_METRICS: "Access operational Prometheus metrics and telemetry summaries",
    PERM_OBSERVABILITY_HEALTH: "Inspect deep infrastructure and dependency health",
    # Background Jobs
    PERM_JOBS_READ: "View background jobs status, execution logs, and diagnostics",
    PERM_JOBS_CREATE: "Enqueue new background jobs",
    PERM_JOBS_CANCEL: "Cancel pending or running background jobs",
    PERM_JOBS_RETRY: "Manually retry failed or dead-lettered background jobs",
    PERM_JOBS_ADMIN: "Full administrative control over queues and workers",
    # Agents
    PERM_AGENTS_READ: "View agent sessions, plans, steps, and telemetry",
    PERM_AGENTS_CREATE: "Create new bounded agent sessions and plans",
    PERM_AGENTS_EXECUTE: "Execute agent sessions and step tool calls",
    PERM_AGENTS_CANCEL: "Cancel running or planned agent sessions",
    PERM_AGENTS_APPROVE: "Approve or reject sensitive agent tool actions",
    PERM_AGENTS_RESUME: "Resume paused or checkpointed agent sessions",
    # Memory
    PERM_MEMORY_READ: "Read tenant and user scoped agent memory items",
    PERM_MEMORY_CREATE: "Store user-declared or derived memory items",
    PERM_MEMORY_UPDATE: "Update or supersede existing memory items",
    PERM_MEMORY_DELETE: "Soft-delete or purge memory items (right-to-delete)",
    PERM_MEMORY_ADMIN: "Administer organization memory policies and retention",
    # Semantic Catalog & Layer (TASK 28)
    PERM_SEMANTIC_READ: "Read semantic catalog, business terms, metrics, dimensions, and mappings",
    PERM_SEMANTIC_CREATE: "Create business terms, metrics, dimensions, entities, and mappings",
    PERM_SEMANTIC_UPDATE: "Update draft or review semantic definitions and metadata",
    PERM_SEMANTIC_DELETE: "Delete or archive semantic catalog objects",
    PERM_SEMANTIC_VERIFY: "Verify and certify semantic column mappings and relationships",
    PERM_SEMANTIC_PUBLISH: "Publish reviewed semantic models to production catalog",
    # Knowledge Graph & Relationship Reasoning (TASK 29)
    PERM_GRAPH_READ: "Read knowledge graph nodes, edges, aliases, and topology",
    PERM_GRAPH_CREATE: "Create knowledge graph nodes, edges, and aliases",
    PERM_GRAPH_UPDATE: "Update knowledge graph nodes, edges, and aliases",
    PERM_GRAPH_DELETE: "Delete or archive knowledge graph nodes and edges",
    PERM_GRAPH_TRAVERSE: "Perform bounded graph traversal and path reasoning",
    PERM_GRAPH_PUBLISH: "Publish knowledge graph edges and nodes to production graph",
    # LLM Gateway & Provider Management
    PERM_LLM_READ: "Inspect LLM models, providers, and health statuses",
    PERM_LLM_MANAGE: "Configure LLM provider adapters, credentials, and global gateway settings",
    PERM_LLM_POLICY_READ: "Read tenant LLM routing, residency, and cost policies",
    PERM_LLM_POLICY_UPDATE: "Update tenant LLM routing, residency, and cost policies",
    PERM_LLM_MODEL_APPROVE: "Approve AI models for enterprise routing and execution",
    PERM_LLM_MODEL_DISABLE: "Disable or deprecate AI models in the registry",
    PERM_LLM_USAGE_READ: "Inspect metered LLM request ledgers, tokens, and cost accounting",
    # Enterprise Response Orchestration (TASK 31)
    PERM_ORCHESTRATION_EXECUTE: "Execute canonical enterprise multi-modal AI queries and decisions",
    PERM_ORCHESTRATION_READ: "Inspect orchestration execution status, plans, steps, and provenance",
    PERM_ORCHESTRATION_MANAGE: "Configure enterprise orchestration thresholds, policies, and overrides",
    # Governance & Human-in-the-Loop Workflow (TASK 32)
    PERM_GOVERNANCE_READ: "Read governance approval requests, risk assessments, and policies",
    PERM_GOVERNANCE_CREATE: "Create governance approval requests for controlled operations",
    PERM_GOVERNANCE_REVIEW: "Review approval requests and submit review comments or vote recommendations",
    PERM_GOVERNANCE_APPROVE: "Grant formal approval decisions and votes on governed requests",
    PERM_GOVERNANCE_REJECT: "Reject governed approval requests or request changes",
    PERM_GOVERNANCE_MANAGE_POLICY: "Create, update, and manage organization governance policies",
    PERM_GOVERNANCE_VIEW_AUDIT: "Inspect immutable governance decision records and audit provenance",
    # Site Reliability Engineering & Operations (TASK 37)
    PERM_SRE_ALERT_READ: "Read operational alerts, fingerprints, and dedup statuses",
    PERM_SRE_ALERT_MANAGE: "Acknowledge, suppress, and resolve operational alerts",
    PERM_SRE_INCIDENT_READ: "Read incident records, timelines, ownership, and MTTR/MTTA",
    PERM_SRE_INCIDENT_MANAGE: "Create incidents, transition FSM lifecycle, and assign responders",
    PERM_SRE_RUNBOOK_READ: "View diagnostic runbooks, safe actions, and symptoms",
    PERM_SRE_RUNBOOK_MANAGE: "Create, update, version, and publish diagnostic runbooks",
    PERM_SRE_SLO_READ: "Read SLI definitions, SLO objectives, and error budgets",
    PERM_SRE_SLO_MANAGE: "Configure and manage SLI and SLO targets and thresholds",
    PERM_SRE_MAINTENANCE_MANAGE: "Create, update, and manage scheduled maintenance windows",
    PERM_SRE_RELEASE_GATE_READ: "Evaluate and view deployment release safety gates",
    # Reliability
    PERM_RELIABILITY_READ: "View chaos scenarios, historical runs, and reliability reports",
    PERM_RELIABILITY_RUN: "Trigger non-production chaos engineering scenario runs",
    PERM_RELIABILITY_MANAGE: "Create, configure, and manage chaos scenarios and parameters",
    PERM_RELIABILITY_READINESS: "Evaluate and view production readiness assessments and scorecards",
    # Enterprise Security & Compliance Governance (TASK 39)
    PERM_COMPLIANCE_READ: "View compliance controls, assessments, posture, and readiness",
    PERM_COMPLIANCE_ASSESS: "Execute continuous compliance assessments over active evidence",
    PERM_COMPLIANCE_MANAGE: "Create and update controls, policies, legal holds, and classifications",
    PERM_COMPLIANCE_EVIDENCE_READ: "View immutable compliance verification evidence and hashes",
    PERM_COMPLIANCE_EVIDENCE_MANAGE: "Ingest and verify immutable compliance verification evidence",
    PERM_COMPLIANCE_FINDINGS_READ: "Inspect security findings, severities, and vulnerabilities",
    PERM_COMPLIANCE_FINDINGS_MANAGE: "Record, assign, and manage security vulnerability findings",
    PERM_COMPLIANCE_ACCESS_REVIEW: "Initiate and participate in periodic access review campaigns",
    PERM_COMPLIANCE_RETENTION_MANAGE: "Configure data retention schedules and deletion policies",
    PERM_COMPLIANCE_PRIVACY_MANAGE: "Manage data subject privacy requests and right-to-delete workflows",
    PERM_COMPLIANCE_RISK_ACCEPTANCE: "Formally accept risk for identified security findings",
    PERM_COMPLIANCE_SECURITY_ADMIN: "Full administrative authority over enterprise security policies and posture",
    # Enterprise FinOps, AI Cost Governance & Usage Optimization (TASK 40)
    PERM_FINOPS_READ: "Read FinOps dashboards, usage ledgers, and cost summaries",
    PERM_FINOPS_MANAGE: "General FinOps administration and cost management",
    PERM_FINOPS_BUDGET_READ: "View organization and scoped budgets, spending, and burn rates",
    PERM_FINOPS_BUDGET_MANAGE: "Create, update, and configure hierarchical financial budgets",
    PERM_FINOPS_QUOTA_MANAGE: "Configure request, token, and spending quotas and enforcement modes",
    PERM_FINOPS_PRICING_MANAGE: "Manage versioned model pricing registries and effective date windows",
    PERM_FINOPS_ANOMALY_READ: "Inspect cost surges, token spikes, and anomaly alerts",
    PERM_FINOPS_POLICY_MANAGE: "Configure hard spending limits and cost enforcement policies",
    PERM_FINOPS_RECONCILIATION_READ: "Inspect gateway-to-ledger reconciliation reports and discrepancy audits",
    PERM_FINOPS_OPTIMIZATION_READ: "View evidence-based AI cost optimization and caching recommendations",
}

# ---------------------------------------------------------------------------
# Default Role Names & Descriptions
# ---------------------------------------------------------------------------

ROLE_ADMIN: Final[str] = "Admin"
ROLE_ANALYST: Final[str] = "Analyst"
ROLE_VIEWER: Final[str] = "Viewer"

SYSTEM_ROLES: Final[dict[str, str]] = {
    ROLE_ADMIN: "Full administrative access to all organization resources and security policies",
    ROLE_ANALYST: "Operational data analytics, reporting, and AI conversational workflows",
    ROLE_VIEWER: "Read-only visibility into datasets, documents, and generated reports",
}

# ---------------------------------------------------------------------------
# Default Role-to-Permission Mappings
# ---------------------------------------------------------------------------

DEFAULT_ROLE_PERMISSIONS: Final[dict[str, set[str]]] = {
    ROLE_ADMIN: set(SYSTEM_PERMISSIONS.keys()),
    ROLE_ANALYST: {
        PERM_ORGANIZATION_READ,
        PERM_DOCUMENTS_READ,
        PERM_DOCUMENTS_WRITE,
        PERM_DATASETS_READ,
        PERM_DATASETS_WRITE,
        PERM_DATA_SOURCES_READ,
        PERM_REPORTS_READ,
        PERM_REPORTS_CREATE,
        PERM_REPORTS_UPDATE,
        PERM_REPORTS_PUBLISH,
        PERM_REPORTS_EXPORT,
        PERM_REPORTS_ARCHIVE,
        PERM_ANALYTICS_READ,
        PERM_ANALYTICS_EXECUTE,
        PERM_AI_CHAT,
        PERM_AI_ANALYZE,
        PERM_EVALUATION_READ,
        PERM_EVALUATION_CREATE,
        PERM_EVALUATION_RUN,
        PERM_EVALUATION_COMPARE,
        PERM_OBSERVABILITY_READ,
        PERM_OBSERVABILITY_HEALTH,
        PERM_JOBS_READ,
        PERM_JOBS_CREATE,
        PERM_JOBS_CANCEL,
        PERM_JOBS_RETRY,
        PERM_AGENTS_READ,
        PERM_AGENTS_CREATE,
        PERM_AGENTS_EXECUTE,
        PERM_AGENTS_CANCEL,
        PERM_AGENTS_APPROVE,
        PERM_AGENTS_RESUME,
        PERM_MEMORY_READ,
        PERM_MEMORY_CREATE,
        PERM_MEMORY_UPDATE,
        PERM_MEMORY_DELETE,
        PERM_DATASOURCE_READ,
        PERM_DATASOURCE_TEST,
        PERM_DATASOURCE_QUERY,
        PERM_DATASOURCE_SYNC,
        PERM_DATASOURCE_SCHEMA,
        PERM_DATASET_READ,
        PERM_DATASET_INGEST,
        PERM_DATASET_PROFILE,
        PERM_DATASET_VERSIONS,
        PERM_SEMANTIC_READ,
        PERM_SEMANTIC_CREATE,
        PERM_SEMANTIC_UPDATE,
        PERM_SEMANTIC_VERIFY,
        PERM_GRAPH_READ,
        PERM_GRAPH_CREATE,
        PERM_GRAPH_UPDATE,
        PERM_GRAPH_TRAVERSE,
        PERM_LLM_READ,
        PERM_LLM_POLICY_READ,
        PERM_LLM_USAGE_READ,
        PERM_ORCHESTRATION_EXECUTE,
        PERM_ORCHESTRATION_READ,
        PERM_GOVERNANCE_READ,
        PERM_GOVERNANCE_CREATE,
        PERM_GOVERNANCE_REVIEW,
        PERM_GOVERNANCE_VIEW_AUDIT,
        PERM_EVALUATION_MONITOR_READ,
        PERM_EVALUATION_BENCHMARK_MANAGE,
        PERM_EVALUATION_RUN_EXECUTE,
        PERM_EVALUATION_QUALITY_GATE_READ,
        PERM_EVALUATION_HUMAN_REVIEW,
        PERM_SRE_ALERT_READ,
        PERM_SRE_INCIDENT_READ,
        PERM_SRE_RUNBOOK_READ,
        PERM_SRE_SLO_READ,
        PERM_SRE_RELEASE_GATE_READ,
        PERM_RELIABILITY_READ,
        PERM_RELIABILITY_READINESS,
        PERM_COMPLIANCE_READ,
        PERM_COMPLIANCE_EVIDENCE_READ,
        PERM_COMPLIANCE_FINDINGS_READ,
        PERM_COMPLIANCE_ASSESS,
        PERM_FINOPS_READ,
        PERM_FINOPS_BUDGET_READ,
        PERM_FINOPS_ANOMALY_READ,
        PERM_FINOPS_RECONCILIATION_READ,
        PERM_FINOPS_OPTIMIZATION_READ,
    },
    ROLE_VIEWER: {
        PERM_ORGANIZATION_READ,
        PERM_DOCUMENTS_READ,
        PERM_DATASETS_READ,
        PERM_DATASET_READ,
        PERM_REPORTS_READ,
        PERM_ANALYTICS_READ,
        PERM_AI_CHAT,
        PERM_EVALUATION_READ,
        PERM_EVALUATION_MONITOR_READ,
        PERM_EVALUATION_QUALITY_GATE_READ,
        PERM_JOBS_READ,
        PERM_AGENTS_READ,
        PERM_MEMORY_READ,
        PERM_DATASOURCE_READ,
        PERM_SEMANTIC_READ,
        PERM_GRAPH_READ,
        PERM_GRAPH_TRAVERSE,
        PERM_LLM_READ,
        PERM_LLM_USAGE_READ,
        PERM_ORCHESTRATION_EXECUTE,
        PERM_ORCHESTRATION_READ,
        PERM_GOVERNANCE_READ,
        PERM_GOVERNANCE_VIEW_AUDIT,
        PERM_SRE_ALERT_READ,
        PERM_SRE_INCIDENT_READ,
        PERM_SRE_RUNBOOK_READ,
        PERM_SRE_SLO_READ,
        PERM_SRE_RELEASE_GATE_READ,
        PERM_RELIABILITY_READ,
        PERM_COMPLIANCE_READ,
        PERM_COMPLIANCE_EVIDENCE_READ,
        PERM_COMPLIANCE_FINDINGS_READ,
        PERM_FINOPS_READ,
        PERM_FINOPS_BUDGET_READ,
    },
}

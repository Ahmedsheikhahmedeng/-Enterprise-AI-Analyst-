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

# Datasets
PERM_DATASETS_READ: Final[str] = "datasets.read"
PERM_DATASETS_WRITE: Final[str] = "datasets.write"
PERM_DATASETS_DELETE: Final[str] = "datasets.delete"

# Data Sources
PERM_DATA_SOURCES_READ: Final[str] = "data_sources.read"
PERM_DATA_SOURCES_WRITE: Final[str] = "data_sources.write"
PERM_DATA_SOURCES_DELETE: Final[str] = "data_sources.delete"

# Reports
PERM_REPORTS_READ: Final[str] = "reports.read"
PERM_REPORTS_CREATE: Final[str] = "reports.create"
PERM_REPORTS_UPDATE: Final[str] = "reports.update"
PERM_REPORTS_DELETE: Final[str] = "reports.delete"

# Analytics
PERM_ANALYTICS_READ: Final[str] = "analytics.read"
PERM_ANALYTICS_EXECUTE: Final[str] = "analytics.execute"

# AI
PERM_AI_CHAT: Final[str] = "ai.chat"
PERM_AI_ANALYZE: Final[str] = "ai.analyze"

# Audit & Usage
PERM_AUDIT_READ: Final[str] = "audit.read"
PERM_USAGE_READ: Final[str] = "usage.read"

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
    # Data Sources
    PERM_DATA_SOURCES_READ: "View external data source connections",
    PERM_DATA_SOURCES_WRITE: "Configure and update data source connections",
    PERM_DATA_SOURCES_DELETE: "Remove external data sources",
    # Reports
    PERM_REPORTS_READ: "View generated enterprise reports",
    PERM_REPORTS_CREATE: "Generate new analytical reports",
    PERM_REPORTS_UPDATE: "Edit existing reports and notes",
    PERM_REPORTS_DELETE: "Delete analytical reports",
    # Analytics
    PERM_ANALYTICS_READ: "View analytics runs and dashboards",
    PERM_ANALYTICS_EXECUTE: "Execute analytical queries and calculations",
    # AI
    PERM_AI_CHAT: "Participate in AI conversations and queries",
    PERM_AI_ANALYZE: "Execute automated AI analytical deep dives",
    # Audit & Usage
    PERM_AUDIT_READ: "Inspect organization audit trails",
    PERM_USAGE_READ: "Inspect platform consumption and token usage",
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
        PERM_ANALYTICS_READ,
        PERM_ANALYTICS_EXECUTE,
        PERM_AI_CHAT,
        PERM_AI_ANALYZE,
    },
    ROLE_VIEWER: {
        PERM_ORGANIZATION_READ,
        PERM_DOCUMENTS_READ,
        PERM_DATASETS_READ,
        PERM_REPORTS_READ,
        PERM_ANALYTICS_READ,
        PERM_AI_CHAT,
    },
}

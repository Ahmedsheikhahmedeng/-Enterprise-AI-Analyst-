"""Secure SQL Agent & Structured Data Analysis module."""

from app.sql_agent.analyzer import SQLResultAnalyzer
from app.sql_agent.config import SQLAgentConfig, get_sql_agent_config
from app.sql_agent.exceptions import (
    SQLAgentError,
    SQLConfigurationError,
    SQLDataSourceNotFoundError,
    SQLProviderError,
    SQLResultSizeExceededError,
    SQLSecurityViolationError,
    SQLTenantMismatchError,
    SQLTimeoutError,
    SQLValidationError,
)
from app.sql_agent.executor import ReadOnlySQLExecutor
from app.sql_agent.models import (
    ColumnSchema,
    GeneratedSQL,
    RelationshipSchema,
    SchemaContext,
    SQLAgentResult,
    SQLComplexityMetrics,
    SQLProvenance,
    SQLQueryResult,
    StructuredAnalysisResult,
    TableSchema,
)
from app.sql_agent.planner import SQLPlan, SQLPlanner
from app.sql_agent.provenance import SQLProvenanceTracker
from app.sql_agent.schema import SchemaDiscoveryService
from app.sql_agent.schemas import (
    SQLAgentRequest,
    SQLAgentResponse,
    SQLAnalysisResponse,
    SQLProvenanceResponse,
    SQLQueryResultResponse,
)
from app.sql_agent.service import SQLAgentService
from app.sql_agent.validator import SQLSecurityValidator

__all__ = [
    "ColumnSchema",
    "GeneratedSQL",
    "ReadOnlySQLExecutor",
    "RelationshipSchema",
    "SQLAgentError",
    "SQLAgentConfig",
    "SQLAgentRequest",
    "SQLAgentResponse",
    "SQLAgentResult",
    "SQLAgentService",
    "SQLAnalysisResponse",
    "SQLComplexityMetrics",
    "SQLConfigurationError",
    "SQLDataSourceNotFoundError",
    "SQLPlan",
    "SQLPlanner",
    "SQLProvenance",
    "SQLProvenanceResponse",
    "SQLProvenanceTracker",
    "SQLProviderError",
    "SQLQueryResult",
    "SQLQueryResultResponse",
    "SQLResultAnalyzer",
    "SQLResultSizeExceededError",
    "SQLSecurityValidator",
    "SQLSecurityViolationError",
    "SQLTenantMismatchError",
    "SQLTimeoutError",
    "SQLValidationError",
    "SchemaContext",
    "SchemaDiscoveryService",
    "StructuredAnalysisResult",
    "TableSchema",
    "get_sql_agent_config",
]

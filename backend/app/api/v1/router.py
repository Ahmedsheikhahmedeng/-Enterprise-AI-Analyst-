from fastapi import APIRouter

from app.api.v1 import health
from app.api.v1.agents import router as agents_router
from app.api.v1.analyst import router as analyst_router
from app.api.v1.evaluation import router as evaluation_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.memory import router as memory_router
from app.api.v1.observability import router as observability_router
from app.api.v1.platform import platform_router
from app.api.v1.query import router as query_router
from app.api.v1.rag import router as rag_router
from app.api.v1.reports import router as reports_router
from app.api.v1.retrieval import router as retrieval_router
from app.api.v1.security import router as security_router
from app.api.v1.sql import router as sql_router
from app.api.v1.vectorstore import router as vectorstore_router
from app.auth.router import router as auth_router
from app.compliance.api import router as compliance_router
from app.connectors.api import router as connectors_router
from app.continuous_evaluation.api import router as continuous_evaluation_router
from app.documents.router import router as documents_router
from app.finops.api import router as finops_router
from app.governance.api import router as governance_router
from app.ingestion.api import router as datasets_router
from app.knowledge_graph.api import graph_router
from app.llm_gateway.api import router as llm_router
from app.product.api import product_router
from app.rbac.router import admin_router, rbac_router
from app.reliability.api import reliability_router
from app.semantic.api import router as semantic_router
from app.sre import sre_router
from app.tenancy.router import tenant_router

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(rbac_router)
api_v1_router.include_router(tenant_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(vectorstore_router)
api_v1_router.include_router(retrieval_router)
api_v1_router.include_router(query_router)
api_v1_router.include_router(rag_router)
api_v1_router.include_router(sql_router)
api_v1_router.include_router(analyst_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(evaluation_router)
api_v1_router.include_router(observability_router)
api_v1_router.include_router(security_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(agents_router)
api_v1_router.include_router(memory_router)
api_v1_router.include_router(connectors_router)
api_v1_router.include_router(datasets_router)
api_v1_router.include_router(semantic_router)
api_v1_router.include_router(graph_router)
api_v1_router.include_router(llm_router)
api_v1_router.include_router(platform_router)
api_v1_router.include_router(governance_router)
api_v1_router.include_router(continuous_evaluation_router)
api_v1_router.include_router(sre_router)
api_v1_router.include_router(reliability_router)
api_v1_router.include_router(compliance_router)
api_v1_router.include_router(finops_router)
api_v1_router.include_router(product_router)

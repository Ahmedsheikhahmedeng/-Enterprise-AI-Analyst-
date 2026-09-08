"""Evidence aggregation service curating multi-source findings into a verified, cited bundle."""

import logging
import uuid
from typing import Any

from app.response_orchestration.domain.enums import EvidenceSourceType, EvidenceTrustLevel
from app.response_orchestration.domain.errors import TenantMismatchError
from app.response_orchestration.domain.models import (
    CitationItem,
    EvidenceBundle,
    EvidenceItem,
)

logger = logging.getLogger(__name__)


class EvidenceService:
    """Consolidates heterogeneous data sources with strict tenant verification and normalized citations."""

    def __init__(self, max_evidence: int = 12) -> None:
        self.max_evidence = max_evidence

    def build_bundle(
        self,
        organization_id: uuid.UUID,
        sql_results: list[Any] | None = None,
        rag_results: list[Any] | None = None,
        graph_paths: list[dict[str, Any]] | None = None,
        semantic_plan: Any | None = None,
        memory_items: list[Any] | None = None,
    ) -> tuple[EvidenceBundle, list[CitationItem]]:
        """Assemble multi-modal evidence into unified bundle with [D#], [S#], [G#], [M#] citations."""
        evidence_items: list[EvidenceItem] = []
        citation_items: list[CitationItem] = []

        d_counter = 1
        s_counter = 1
        g_counter = 1
        m_counter = 1

        # 1. SQL Evidence
        if sql_results:
            for sr in sql_results:
                # Check tenant boundary if available on result
                res_org = getattr(sr, "organization_id", None)
                if res_org and str(res_org) != str(organization_id):
                    raise TenantMismatchError(
                        f"Cross-tenant SQL evidence detected: expected {organization_id}, got {res_org}"
                    )

                tag = f"[S{s_counter}]"
                s_counter += 1
                content = ""
                if getattr(sr, "analysis", None) and getattr(sr.analysis, "summary", None):
                    content = sr.analysis.summary
                elif getattr(sr, "query_result", None) and getattr(sr.query_result, "rows", None):
                    first_rows = sr.query_result.rows[:3]
                    content = "; ".join(
                        ", ".join(f"{k}: {v}" for k, v in r.items()) for r in first_rows
                    )
                else:
                    content = "Executed structured SQL query successfully."

                metrics_dict = {}
                if getattr(sr, "analysis", None) and getattr(sr.analysis, "metrics", None):
                    metrics_dict = dict(sr.analysis.metrics)

                item = EvidenceItem(
                    evidence_id=str(uuid.uuid4()),
                    source_type=EvidenceSourceType.SQL,
                    source_id=str(getattr(sr, "datasource_id", "sql-branch")),
                    content=content,
                    trust_level=EvidenceTrustLevel.DIRECT,
                    confidence=0.98,
                    is_calculated=True,
                    citation_id=tag,
                    metadata={"metrics": metrics_dict, "sql": getattr(sr, "generated_sql", "")},
                )
                evidence_items.append(item)
                citation_items.append(
                    CitationItem(
                        citation_id=tag,
                        source_type=EvidenceSourceType.SQL,
                        source_id=item.source_id,
                        title="Structured Database Calculation",
                        snippet=content[:200],
                        trust_level=EvidenceTrustLevel.DIRECT,
                    )
                )

        # 2. Semantic Catalog Evidence
        if semantic_plan:
            resolved_metrics = getattr(semantic_plan, "resolved_metrics", [])
            for rm in resolved_metrics:
                tag = f"[M{m_counter}]"
                m_counter += 1
                name = getattr(rm, "name", "metric")
                formula = getattr(rm, "formula", "")
                content = f"Approved Metric '{name}' defined as: {formula}"
                item = EvidenceItem(
                    evidence_id=str(uuid.uuid4()),
                    source_type=EvidenceSourceType.SEMANTIC,
                    source_id=str(getattr(rm, "metric_id", name)),
                    content=content,
                    trust_level=EvidenceTrustLevel.DIRECT,
                    confidence=0.95,
                    is_calculated=False,
                    citation_id=tag,
                    metadata={"formula": formula, "metric_name": name},
                )
                evidence_items.append(item)
                citation_items.append(
                    CitationItem(
                        citation_id=tag,
                        source_type=EvidenceSourceType.SEMANTIC,
                        source_id=item.source_id,
                        title=f"Semantic Definition: {name}",
                        snippet=content,
                        trust_level=EvidenceTrustLevel.DIRECT,
                    )
                )

        # 3. RAG Document Evidence
        if rag_results:
            for rr in rag_results:
                answer_obj = getattr(rr, "answer", None)
                ev_list = getattr(answer_obj, "evidence", []) if answer_obj else []
                for ev in ev_list:
                    # Enforce strict tenant boundary on every chunk
                    chunk_org = getattr(ev, "organization_id", None)
                    if chunk_org and str(chunk_org) != str(organization_id):
                        raise TenantMismatchError(
                            f"Cross-tenant document chunk detected: expected {organization_id}, got {chunk_org}"
                        )

                    tag = f"[D{d_counter}]"
                    d_counter += 1
                    raw_text = getattr(ev, "text", "")
                    doc_title = getattr(ev, "document_name", "Document")
                    item = EvidenceItem(
                        evidence_id=str(getattr(ev, "evidence_id", uuid.uuid4())),
                        source_type=EvidenceSourceType.DOCUMENT,
                        source_id=str(getattr(ev, "document_id", uuid.uuid4())),
                        content=raw_text,
                        trust_level=EvidenceTrustLevel.DIRECT,
                        confidence=float(getattr(ev, "rerank_score", 0.85) or 0.85),
                        is_calculated=False,
                        citation_id=tag,
                        metadata={
                            "document_name": doc_title,
                            "page_number": getattr(ev, "page_number", None),
                        },
                    )
                    evidence_items.append(item)
                    citation_items.append(
                        CitationItem(
                            citation_id=tag,
                            source_type=EvidenceSourceType.DOCUMENT,
                            source_id=item.source_id,
                            title=doc_title,
                            snippet=raw_text[:200],
                            trust_level=EvidenceTrustLevel.DIRECT,
                        )
                    )

        # 4. Knowledge Graph Reasoning Evidence
        if graph_paths:
            for gp in graph_paths:
                tag = f"[G{g_counter}]"
                g_counter += 1
                nodes = gp.get("nodes", [])
                rels = gp.get("relationships", [])
                conf = float(gp.get("confidence", 0.75))
                path_str = " -> ".join(nodes) if nodes else "Graph relation"
                content = f"Verified relationship path: {path_str} (via {', '.join(rels)})"
                item = EvidenceItem(
                    evidence_id=str(uuid.uuid4()),
                    source_type=EvidenceSourceType.GRAPH,
                    source_id="kg-traversal",
                    content=content,
                    trust_level=EvidenceTrustLevel.INFERRED,
                    confidence=conf,
                    is_calculated=False,
                    citation_id=tag,
                    metadata={"nodes": nodes, "relationships": rels},
                )
                evidence_items.append(item)
                citation_items.append(
                    CitationItem(
                        citation_id=tag,
                        source_type=EvidenceSourceType.GRAPH,
                        source_id="kg-traversal",
                        title="Knowledge Graph Reasoning",
                        snippet=content,
                        trust_level=EvidenceTrustLevel.INFERRED,
                    )
                )

        # 5. Agent / User Memory (Classified as UNVERIFIED unless explicitly verified)
        if memory_items:
            for mem in memory_items:
                mem_org = getattr(mem, "organization_id", None)
                if mem_org and str(mem_org) != str(organization_id):
                    raise TenantMismatchError("Cross-tenant memory item access rejected")
                tag = f"[M{m_counter}]"
                m_counter += 1
                content = getattr(mem, "content", str(mem))
                item = EvidenceItem(
                    evidence_id=str(getattr(mem, "id", uuid.uuid4())),
                    source_type=EvidenceSourceType.MEMORY,
                    source_id=str(getattr(mem, "id", "mem")),
                    content=content,
                    trust_level=EvidenceTrustLevel.UNVERIFIED,
                    confidence=0.50,
                    is_calculated=False,
                    citation_id=tag,
                    metadata={"scope": "user_memory"},
                )
                evidence_items.append(item)

        # Cap evidence by max_evidence
        bundle = EvidenceBundle(items=evidence_items[: self.max_evidence])
        return bundle, citation_items[: self.max_evidence]

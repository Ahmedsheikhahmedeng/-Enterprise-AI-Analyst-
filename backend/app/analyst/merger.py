"""Consolidates and namespaces heterogeneous evidence from SQL and RAG branches."""

from app.analyst.models import UnifiedEvidence
from app.rag.models import RAGAnswerResult
from app.sql_agent.models import SQLAgentResult


class EvidenceMerger:
    """Merges structured SQL rows/metrics and unstructured RAG chunks into UnifiedEvidence."""

    def __init__(self, max_evidence: int = 20) -> None:
        self.max_evidence = max_evidence

    def merge(
        self,
        sql_results: list[SQLAgentResult] | None = None,
        rag_results: list[RAGAnswerResult] | None = None,
    ) -> list[UnifiedEvidence]:
        """Merge, namespace, and rank evidence from executed branches."""
        unified: list[UnifiedEvidence] = []
        sql_idx = 1
        rag_idx = 1

        # 1. Process SQL Results (Prefix: S#)
        if sql_results:
            for sr in sql_results:
                # Add overall tabular summary/metrics as primary evidence item
                summary_text = sr.analysis.summary if sr.analysis else ""
                metrics_text = ""
                if sr.analysis and sr.analysis.metrics:
                    metrics_text = f" Computed metrics: {sr.analysis.metrics}"

                primary_sql_text = f"{summary_text}{metrics_text}".strip()
                if not primary_sql_text and sr.query_result.rows:
                    sample_rows = sr.query_result.rows[:5]
                    primary_sql_text = (
                        f"Result records ({sr.query_result.row_count} total): {sample_rows}"
                    )

                tbls = sr.provenance.tables_used
                table_names = ", ".join(tbls) if tbls else "database"
                unified.append(
                    UnifiedEvidence(
                        evidence_id=f"S{sql_idx}",
                        source_type="sql",
                        title=f"SQL Query Result [{table_names}]",
                        text=primary_sql_text or "Empty SQL result",
                        is_calculated=True,
                        metadata={
                            "sql_hash": sr.provenance.sql_hash,
                            "datasource_id": str(sr.provenance.datasource_id),
                            "row_count": sr.query_result.row_count,
                            "tables": sr.provenance.tables_used,
                            "columns": sr.query_result.columns,
                            "metrics": sr.analysis.metrics if sr.analysis else {},
                        },
                        confidence=1.0,
                    )
                )
                sql_idx += 1

                # If individual rows have meaningful data, add as discrete evidence
                for row in sr.query_result.rows[:3]:
                    if len(unified) >= self.max_evidence:
                        break
                    row_repr = ", ".join(f"{k}={v}" for k, v in row.items())
                    unified.append(
                        UnifiedEvidence(
                            evidence_id=f"S{sql_idx}",
                            source_type="sql",
                            title=f"Record [{table_names}]",
                            text=row_repr,
                            is_calculated=True,
                            metadata={
                                "sql_hash": sr.provenance.sql_hash,
                                "datasource_id": str(sr.provenance.datasource_id),
                                "row": row,
                            },
                            confidence=1.0,
                        )
                    )
                    sql_idx += 1

        # 2. Process RAG Results (Prefix: R#)
        if rag_results:
            for rr in rag_results:
                for ev in rr.evidence:
                    if len(unified) >= self.max_evidence:
                        break
                    doc_title = ev.document_name or "Document"
                    page_info = f" (p. {ev.page_number})" if ev.page_number else ""
                    unified.append(
                        UnifiedEvidence(
                            evidence_id=f"R{rag_idx}",
                            source_type="document",
                            title=f"{doc_title}{page_info}",
                            text=ev.text.strip(),
                            is_calculated=False,
                            metadata={
                                "chunk_id": str(ev.chunk_id),
                                "document_id": str(ev.document_id),
                                "page_number": ev.page_number,
                                "heading_path": ev.heading_path,
                                "document_name": ev.document_name,
                                "rerank_score": ev.rerank_score,
                            },
                            confidence=ev.rerank_score if ev.rerank_score is not None else 0.8,
                        )
                    )
                    rag_idx += 1

        return unified[: self.max_evidence]

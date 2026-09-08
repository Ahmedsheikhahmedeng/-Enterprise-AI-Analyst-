"""Context assembly and token budget packing for RAG generation."""

import logging

from app.rag.models import Evidence

logger = logging.getLogger(__name__)


class ContextAssembler:
    """Assembles and formats Evidence items into structured context string within token limits."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count based on whitespace word boundaries with 1.3x safety margin."""
        if not text:
            return 0
        words = len(text.split())
        return max(1, int(words * 1.3))

    def assemble(
        self,
        evidence_list: list[Evidence],
        max_context_tokens: int = 4000,
    ) -> tuple[str, list[Evidence], int]:
        """Format evidence into structured blocks up to max_context_tokens budget.

        Returns:
            Tuple of (formatted_context_text, included_evidence_items, total_estimated_tokens).
        """
        if not evidence_list:
            return "", [], 0

        blocks: list[str] = []
        included_evidence: list[Evidence] = []
        accumulated_tokens = 0

        for ev in evidence_list:
            header_lines = [f"[Evidence {ev.rank}] (ID: {ev.evidence_id})"]
            if ev.document_name:
                header_lines.append(f"Document: {ev.document_name}")
            if ev.section:
                header_lines.append(f"Section: {ev.section}")
            elif ev.heading_path:
                header_lines.append(f"Section: {ev.heading_path}")
            if ev.page_number is not None:
                header_lines.append(f"Page: {ev.page_number}")

            header_str = "\n".join(header_lines)
            block_text = f"{header_str}\nContent:\n{ev.text}\n"

            block_tokens = self.estimate_tokens(block_text)

            # Check if adding this block exceeds maximum context budget
            if blocks and (accumulated_tokens + block_tokens > max_context_tokens):
                logger.info(
                    "Context token budget reached (%d + %d > %d); packing stopped at evidence %s",
                    accumulated_tokens,
                    block_tokens,
                    max_context_tokens,
                    ev.evidence_id,
                )
                break

            blocks.append(block_text)
            included_evidence.append(ev)
            accumulated_tokens += block_tokens

        formatted_context = "\n---\n".join(blocks)
        return formatted_context, included_evidence, accumulated_tokens

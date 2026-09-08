"""Text builder for preparing chunk contents for embedding models."""

from typing import Any

from app.embeddings.normalization import normalize_embedding_text


class EmbeddingTextBuilder:
    """Constructs the final input string fed to embedding providers.

    Features:
    - Combines semantic heading hierarchy with chunk content for richer contextual embeddings.
    - Excludes technical database IDs (UUIDs, tenant IDs, hashes) from the semantic embedding space.
    - Preserves chunk content immutability: the underlying DocumentChunk is never mutated.
    - Normalizes the composite text via Unicode NFKC and whitespace normalization.
    """

    @classmethod
    def build_from_chunk(cls, chunk: Any) -> str:
        """Build embedding input from a DocumentChunk model instance or chunk dict.

        Guarantees: chunk.content is NOT modified.
        """
        heading_context = getattr(chunk, "heading_context", None)
        if heading_context is None and isinstance(chunk, dict):
            heading_context = chunk.get("heading_context")

        content = getattr(chunk, "content", None)
        if content is None and isinstance(chunk, dict):
            content = chunk.get("content", "")

        content_str = str(content) if content is not None else ""
        heading_str = str(heading_context) if heading_context is not None else None
        return cls.build(content=content_str, heading_context=heading_str)

    @classmethod
    def build(cls, content: str, heading_context: str | None = None) -> str:
        """Combine heading context and content into a cohesive normalized string.

        Example:
            heading_context: "Financial Performance > Revenue"
            content: "Revenue increased by 15% in 2025."
            Result:
                "Financial Performance > Revenue\n\nRevenue increased by 15% in 2025."
        """
        parts: list[str] = []
        if heading_context and heading_context.strip():
            clean_heading = heading_context.strip()
            parts.append(clean_heading)

        if content and content.strip():
            clean_content = content.strip()
            parts.append(clean_content)

        raw_combined = "\n\n".join(parts)
        return normalize_embedding_text(raw_combined)

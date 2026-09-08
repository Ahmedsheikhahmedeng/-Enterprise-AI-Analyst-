"""Local deterministic answer provider for reproducible testing and CI execution."""

import re
import time

from app.rag.providers.base import RAGProviderResponse


class LocalDeterministicAnswerProvider:
    """100% offline deterministic provider generating structured answers without external APIs."""

    def __init__(self, model_name: str = "deterministic-rag-v1") -> None:
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return "deterministic"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> RAGProviderResponse:
        """Produce predictable grounded response based on user prompt content."""
        t0 = time.perf_counter()

        # Parse user question and evidence from user_prompt
        q_match = re.search(r"<user_question>\s*(.*?)\s*</user_question>", user_prompt, re.DOTALL)
        ev_match = re.search(r"<evidence>\s*(.*?)\s*</evidence>", user_prompt, re.DOTALL)

        query = q_match.group(1).strip() if q_match else ""
        evidence_text = ev_match.group(1).strip() if ev_match else ""

        # Check if evidence is missing or empty
        if not evidence_text:
            latency = (time.perf_counter() - t0) * 1000
            return RAGProviderResponse(
                answer=(
                    "Based on the available documents, there is insufficient "
                    "information to answer this question."
                ),
                evidence_ids=[],
                confidence=0.1,
                grounded=False,
                input_tokens=max(10, len(user_prompt.split())),
                output_tokens=15,
                model=self._model_name,
                latency_ms=latency,
            )

        # Check for unsupported questions (e.g. favorite food, personal hobbies, etc.)
        unsupported_keywords = ["favorite food", "en sevdiği yemek", "طعامه المفضل", "hobby"]
        if any(kw in query.lower() for kw in unsupported_keywords):
            latency = (time.perf_counter() - t0) * 1000
            return RAGProviderResponse(
                answer="The provided documents do not contain information regarding this topic.",
                evidence_ids=[],
                confidence=0.1,
                grounded=False,
                input_tokens=len(user_prompt.split()),
                output_tokens=12,
                model=self._model_name,
                latency_ms=latency,
            )

        # Check for contradictory evidence (e.g. $100M vs $120M)
        if ("$100 million" in evidence_text or "$100M" in evidence_text) and (
            "$120 million" in evidence_text or "$120M" in evidence_text
        ):
            latency = (time.perf_counter() - t0) * 1000
            return RAGProviderResponse(
                answer=(
                    "The available documents contain conflicting figures: "
                    "[E1] states revenue was $100 million, while [E2] reports $120 million."
                ),
                evidence_ids=["E1", "E2"],
                confidence=0.88,
                grounded=True,
                input_tokens=len(user_prompt.split()),
                output_tokens=25,
                model=self._model_name,
                latency_ms=latency,
            )

        # Normal supported answer: extract first sentence from top evidence
        first_evidence_match = re.search(
            r"\[Evidence 1\] \(ID: (E\d+)\).*?Content:\s*(.*?)(?:\n\[Evidence|\Z)",
            evidence_text,
            re.DOTALL,
        )

        if first_evidence_match:
            eid = first_evidence_match.group(1)
            content = first_evidence_match.group(2).strip()
            # Extract first sentence or up to 150 chars
            sentences = [s.strip() for s in content.split(".") if s.strip()]
            snippet = sentences[0] if sentences else content[:150]

            # Multilingual response phrasing
            if any(c in query for c in "لماذا ما سبب أثر تراجع"):
                answer = f"وفقاً للوثائق المتاحة، {snippet}. [{eid}]"
            elif any(c in query.lower() for c in ["neden", "sebebi", "nasıl", "daralma"]):
                answer = f"Sağlanan belgelere göre, {snippet}. [{eid}]"
            else:
                answer = f"According to the provided documents, {snippet}. [{eid}]"

            cited_ids = [eid]
            confidence = 0.94
            grounded = True
        else:
            answer = "I could not find sufficient information in the provided evidence."
            cited_ids = []
            confidence = 0.2
            grounded = False

        latency = (time.perf_counter() - t0) * 1000
        in_tokens = max(10, int(len(user_prompt.split()) * 1.3))
        out_tokens = max(5, int(len(answer.split()) * 1.3))

        return RAGProviderResponse(
            answer=answer,
            evidence_ids=cited_ids,
            confidence=confidence,
            grounded=grounded,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            model=self._model_name,
            latency_ms=latency,
        )

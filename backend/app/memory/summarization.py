"""Summarization service for compressing conversation history and agent sessions."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StructuredSessionSummary:
    """Concise extraction of key outcomes, verified facts, and decisions from a session."""

    summary: str
    key_facts: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


class MemorySummarizer:
    """Summarizes dialogs or tool executions into structured, non-hallucinatory outcomes."""

    @staticmethod
    def summarize_conversation(messages: list[dict[str, Any]]) -> StructuredSessionSummary:
        """Generate structured summary from dialogue history."""
        if not messages:
            return StructuredSessionSummary(summary="Empty conversation thread.")

        user_queries: list[str] = []
        assistant_answers: list[str] = []
        key_facts: list[str] = []
        decisions: list[str] = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "").strip()
            if not content:
                continue

            if role == "user":
                user_queries.append(content)
            elif role == "assistant":
                assistant_answers.append(content[:150] + ("..." if len(content) > 150 else ""))

            if "prefer" in content.lower() or "decided" in content.lower():
                decisions.append(content[:200])
            if any(
                kw in content.lower()
                for kw in ["total", "rate", "increased", "decreased", "metric", "revenue"]
            ):
                key_facts.append(content[:200])

        last_query = user_queries[-1] if user_queries else "N/A"
        summary_text = (
            f"User engaged in {len(messages)} interaction(s). "
            f"Primary query topic: '{last_query[:100]}'."
        )

        return StructuredSessionSummary(
            summary=summary_text,
            key_facts=key_facts[:5],
            decisions=decisions[:3],
            open_questions=[],
        )

    @staticmethod
    def summarize_agent_session(
        goal: str,
        steps: list[dict[str, Any]],
        final_answer: str | None = None,
    ) -> StructuredSessionSummary:
        """Generate structured summary from completed agent plan steps."""
        tools_run = [str(s.get("tool_name", "unknown")) for s in steps]
        facts: list[str] = []
        for step in steps:
            output = step.get("output", {})
            if isinstance(output, dict) and "answer" in output:
                facts.append(str(output["answer"])[:200])

        summary_text = (
            f"Agent completed goal: '{goal[:120]}'. "
            f"Executed {len(steps)} step(s) with tools: {', '.join(set(tools_run))}."
        )

        decisions = [f"Goal fulfilled: {goal}"] if final_answer else []

        return StructuredSessionSummary(
            summary=summary_text,
            key_facts=facts[:5],
            decisions=decisions,
            open_questions=[],
        )

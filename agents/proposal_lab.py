"""Source-grounded research proposal drafting."""

from dataclasses import dataclass, asdict
from typing import Any

from agents.gap_finder import Gap
from agents.reader import Summary
from core.llm import LLMClient


@dataclass
class ProposalDraft:
    """A research concept whose sections retain supporting source IDs."""

    title: str
    motivation: str
    research_question: str
    hypothesis: str
    proposed_method: str
    evaluation_plan: str
    risks: str
    source_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable proposal."""
        return asdict(self)


class ProposalLab:
    """Draft a proposal strictly from a verified research context."""

    def __init__(self, llm: LLMClient) -> None:
        """Initialize the proposal language model."""
        self.llm = llm

    def draft(self, topic: str, summaries: list[Summary], gaps: list[Gap]) -> ProposalDraft:
        """Create a proposal draft with source IDs and conservative fallbacks."""
        source_ids = [summary.source_id for summary in summaries]
        context = "\n\n".join(
            f"SOURCE_ID: {summary.source_id}\nPROBLEM: {summary.problem}\n"
            f"METHOD: {summary.method}\nRESULTS: {summary.results}\n"
            f"LIMITATIONS: {summary.limitations}"
            for summary in summaries
        )
        gap_text = "\n".join(f"GAP: {gap.claim} | SOURCES: {', '.join(gap.source_ids)}" for gap in gaps)
        response = self.llm.complete(
            "You are a research proposal architect. Use only the supplied evidence. "
            "Do not invent results, citations, datasets, or numbers. Return exactly "
            "eight labeled lines: TITLE, MOTIVATION, RESEARCH_QUESTION, HYPOTHESIS, "
            "PROPOSED_METHOD, EVALUATION_PLAN, RISKS, SOURCE_IDS. Use 'not found' "
            "when unsupported. SOURCE_IDS must contain only supplied IDs.\n"
            f"TOPIC: {topic}\n{context}\n{gap_text}"
        )
        values = self._parse(response)
        if all(value == "not found" for value in values.values() if isinstance(value, str)):
            values = self._fallback(topic, summaries, gaps)
        values["source_ids"] = [value for value in values.get("source_ids", []) if value in source_ids]
        return ProposalDraft(**values)

    @staticmethod
    def _parse(response: str) -> dict[str, Any]:
        """Parse labeled proposal output."""
        fields = {
            "title": "not found",
            "motivation": "not found",
            "research_question": "not found",
            "hypothesis": "not found",
            "proposed_method": "not found",
            "evaluation_plan": "not found",
            "risks": "not found",
            "source_ids": [],
        }
        names = {key.upper(): key for key in fields}
        for line in response.splitlines():
            if ":" not in line:
                continue
            label, value = line.split(":", 1)
            key = names.get(label.strip().upper())
            if not key:
                continue
            if key == "source_ids":
                fields[key] = [item.strip() for item in value.split(",") if item.strip()]
            elif value.strip():
                fields[key] = value.strip()
        return fields

    @staticmethod
    def _fallback(topic: str, summaries: list[Summary], gaps: list[Gap]) -> dict[str, Any]:
        """Create a transparent proposal when no model response is available."""
        source_ids = [summary.source_id for summary in summaries]
        gap = gaps[0].claim if gaps else "not found"
        return {
            "title": f"Investigating {topic}",
            "motivation": summaries[0].problem if summaries else "not found",
            "research_question": f"How can the gap '{gap}' be investigated?",
            "hypothesis": "not found",
            "proposed_method": summaries[0].method if summaries else "not found",
            "evaluation_plan": "not found",
            "risks": "Claims remain provisional until tested against new evidence.",
            "source_ids": source_ids,
        }

"""Research-gap proposal agent."""

from dataclasses import dataclass, asdict
from typing import Any

from agents.reader import Summary
from core.llm import LLMClient


@dataclass
class Gap:
    """A proposed gap and the source IDs supporting it."""

    claim: str
    source_ids: list[str]


class GapFinder:
    """Compare paper summaries and return source-linked gaps."""

    def __init__(self, llm: LLMClient) -> None:
        """Initialize the language model."""
        self.llm = llm

    def find(self, summaries: list[Summary]) -> list[Gap]:
        """Generate gaps, requiring source IDs in each returned record."""
        if not summaries:
            return []
        context = "\n\n".join(
            f"SOURCE_ID={item.source_id}\n{item.problem}\n{item.method}\n{item.limitations}"
            for item in summaries
        )
        response = self.llm.complete(
            "Identify research gaps only from these summaries. Format each line as "
            "GAP: claim | SOURCES: source_id,source_id. Do not invent IDs.\n" + context
        )
        known = {item.source_id for item in summaries}
        gaps: list[Gap] = []
        for line in response.splitlines():
            if not line.startswith("GAP:") or "| SOURCES:" not in line:
                continue
            claim, sources = line[4:].split("| SOURCES:", 1)
            source_ids = [value.strip() for value in sources.split(",") if value.strip() in known]
            if claim.strip() and source_ids:
                gaps.append(Gap(claim=claim.strip(), source_ids=source_ids))
        return gaps

    @staticmethod
    def to_dicts(gaps: list[Gap]) -> list[dict[str, Any]]:
        """Convert gaps to serializable dictionaries."""
        return [asdict(gap) for gap in gaps]

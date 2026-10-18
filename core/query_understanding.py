"""Natural-language research request understanding."""

from dataclasses import asdict, dataclass
import json
import re
from typing import Any

from core.llm import LLMClient


@dataclass
class ResearchIntent:
    """Structured meaning extracted from a user's research request."""

    original_query: str
    topic: str
    intent: str
    subtopics: list[str]
    constraints: list[str]
    year_from: int | None
    year_to: int | None
    requested_limit: int | None
    confidence: float
    method: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


class QueryInterpreter:
    """Convert a natural-language request into a safe research brief."""

    def __init__(self, llm: LLMClient) -> None:
        """Initialize the interpreter with the configured language model."""
        self.llm = llm

    def interpret(self, query: str) -> ResearchIntent:
        """Interpret a request with the LLM and use deterministic fallback parsing."""
        cleaned = " ".join(query.split()).strip()
        if not cleaned:
            return self._fallback("not found")
        try:
            response = self.llm.complete(self._prompt(cleaned))
        except Exception:
            return self._fallback(cleaned)
        parsed = self._parse_json(response)
        if parsed:
            return self._from_dict(cleaned, parsed)
        return self._fallback(cleaned)

    @staticmethod
    def _prompt(query: str) -> str:
        """Build a strict JSON-only interpretation prompt."""
        return (
            "You are a research query understanding component. Extract intent from "
            "the user's request without answering it or inventing facts. Return only "
            "valid JSON with keys topic, intent, subtopics, constraints, year_from, "
            "year_to, requested_limit, and confidence. The intent must be one of "
            "search, summarize, compare, gaps, verify. Use null when absent.\n\n"
            f"USER REQUEST: {query}"
        )

    @staticmethod
    def _parse_json(response: str) -> dict[str, Any] | None:
        """Parse a JSON object even when a provider adds a code fence."""
        match = re.search(r"\{.*\}", response, flags=re.DOTALL)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    @classmethod
    def _from_dict(cls, query: str, value: dict[str, Any]) -> ResearchIntent:
        """Validate model fields and normalize malformed values safely."""
        intents = {"search", "summarize", "compare", "gaps", "verify"}
        intent = value.get("intent") if value.get("intent") in intents else "search"
        topic = str(value.get("topic") or query).strip() or "not found"
        return ResearchIntent(
            original_query=query,
            topic=topic,
            intent=intent,
            subtopics=cls._strings(value.get("subtopics")),
            constraints=cls._strings(value.get("constraints")),
            year_from=cls._year(value.get("year_from")),
            year_to=cls._year(value.get("year_to")),
            requested_limit=cls._limit(value.get("requested_limit")),
            confidence=max(0.0, min(1.0, cls._number(value.get("confidence"), 0.7))),
            method="llm",
        )

    @classmethod
    def _fallback(cls, query: str) -> ResearchIntent:
        """Extract useful intent without an API key or model response."""
        lowered = query.lower()
        if any(word in lowered for word in ("gap", "future work", "open problem")):
            intent = "gaps"
        elif any(word in lowered for word in ("compare", "versus", " vs ")):
            intent = "compare"
        elif any(word in lowered for word in ("summarize", "summary", "explain")):
            intent = "summarize"
        elif any(word in lowered for word in ("verify", "citation", "source")):
            intent = "verify"
        else:
            intent = "search"
        topic = re.sub(
            r"^(please\s+)?(find|search for|show me|summarize|explain|compare)\s+",
            "",
            query,
            flags=re.IGNORECASE,
        ).strip(" ?.")
        years = [int(value) for value in re.findall(r"\b(19\d{2}|20\d{2})\b", query)]
        limit_match = re.search(r"\b(\d{1,2})\s+(?:papers|articles|studies)\b", lowered)
        return ResearchIntent(
            original_query=query,
            topic=topic or "not found",
            intent=intent,
            subtopics=[],
            constraints=[],
            year_from=min(years) if years else None,
            year_to=max(years) if len(years) > 1 else None,
            requested_limit=int(limit_match.group(1)) if limit_match else None,
            confidence=0.45,
            method="heuristic",
        )

    @staticmethod
    def _strings(value: Any) -> list[str]:
        """Keep only non-empty strings from a model array."""
        return [item.strip() for item in value or [] if isinstance(item, str) and item.strip()]

    @staticmethod
    def _year(value: Any) -> int | None:
        """Normalize a plausible year."""
        try:
            year = int(value)
        except (TypeError, ValueError):
            return None
        return year if 1900 <= year <= 2100 else None

    @staticmethod
    def _limit(value: Any) -> int | None:
        """Normalize a bounded requested result count."""
        try:
            return max(1, min(50, int(value)))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _number(value: Any, default: float) -> float:
        """Convert a model confidence value to a float."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

"""Multi-agent paper explanation and grounded paper chat."""

from dataclasses import dataclass
import re

from agents.reader import Summary
from agents.searcher import Paper
from core.llm import LLMClient


@dataclass
class PaperExplanation:
    """A visualizable explanation of one paper."""

    source_id: str
    title: str
    overview: str
    flowchart_dot: str
    key_terms: list[str]
    stages: list[tuple[str, str]]
    stage_scores: list[int]
    concept_links: list[tuple[str, str, int]]


class PaperExplainer:
    """Coordinate extractor, visualizer, and tutor behaviors for one paper."""

    def __init__(self, llm: LLMClient) -> None:
        """Initialize the grounded language model."""
        self.llm = llm

    def explain(self, paper: Paper, summary: Summary | None) -> PaperExplanation:
        """Create a source-linked overview and a safe flowchart."""
        if summary is None:
            problem, method, results, limitations = self._heuristic_fields(paper.abstract)
            overview = self._overview(paper, problem, method, results)
        else:
            overview = self.llm.complete(
                "Explain this paper in 3 concise, source-grounded sentences. "
                "Do not add facts. Include SOURCE_ID in the answer.\n"
                f"SOURCE_ID: {paper.source_id}\n"
                f"PROBLEM: {summary.problem}\nMETHOD: {summary.method}\n"
                f"RESULTS: {summary.results}\nLIMITATIONS: {summary.limitations}"
            )
            if not overview or overview == "not found":
                overview = self._overview(paper, summary.problem, summary.method, summary.results)
            problem, method, results = summary.problem, summary.method, summary.results
            limitations = summary.limitations
        stages = [
            ("Problem", problem or "not found"),
            ("Method", method or "not found"),
            ("Results", results or "not found"),
            ("Limitations", limitations or "not found"),
        ]
        return PaperExplanation(
            source_id=paper.source_id,
            title=paper.title,
            overview=overview or "not found",
            flowchart_dot=self._dot(problem, method, results),
            key_terms=self._terms(paper.abstract),
            stages=stages,
            stage_scores=[self._score(value) for _, value in stages],
            concept_links=self._concept_links(self._terms(paper.abstract)),
        )

    @staticmethod
    def _overview(paper: Paper, problem: str, method: str, results: str) -> str:
        """Build a detailed grounded overview without inventing claims."""
        return (
            f"{paper.title}. The paper addresses: {problem}. "
            f"It uses: {method}. Reported outcome: {results}. "
            f"SOURCE_ID: {paper.source_id}"
        )

    @staticmethod
    def _heuristic_fields(text: str) -> tuple[str, str, str, str]:
        """Extract conservative fields from an abstract when no summary exists."""
        sentences = [part.strip() for part in text.replace("\n", " ").split(".") if part.strip()]
        if not sentences:
            return ("not found", "not found", "not found", "not found")
        def find(words: tuple[str, ...], default: str) -> str:
            """Find the first sentence containing a keyword."""
            return next((s[:500] for s in sentences if any(w in s.lower() for w in words)), default)
        return (
            sentences[0][:500],
            find(("propose", "method", "approach", "framework", "model"), "not found"),
            find(("result", "show", "achieve", "improve"), "not found"),
            find(("limit", "however", "future"), "not found"),
        )

    @staticmethod
    def _score(value: str) -> int:
        """Estimate how much source text supports a visual stage."""
        return 0 if not value or value == "not found" else min(100, 35 + len(value) // 8)

    @staticmethod
    def _concept_links(terms: list[str]) -> list[tuple[str, str, int]]:
        """Create weighted concept links for a paper concept network."""
        return [(terms[index], terms[index + 1], max(1, 8 - index)) for index in range(len(terms) - 1)]

    def answer(self, paper: Paper, summary: Summary | None, question: str) -> str:
        """Answer a question using only the selected paper's source material."""
        source = summary.source_text if summary else paper.abstract
        if not source or source == "not found":
            return f"SOURCE_ID: {paper.source_id}\nAnswer: not found"
        evidence = self.llm.complete(
            "You are the evidence analyst agent. Extract only passages or facts "
            "that answer the question. If absent, say not found. Include SOURCE_ID.\n"
            f"SOURCE_ID: {paper.source_id}\nQUESTION: {question}\nSOURCE_TEXT:\n{source[:24000]}"
        )
        draft = self.llm.complete(
            "You are the teaching agent. Explain the answer clearly using only the "
            "evidence below. Do not add outside facts. Include SOURCE_ID.\n"
            f"SOURCE_ID: {paper.source_id}\nQUESTION: {question}\nEVIDENCE:\n{evidence}"
        )
        return self.llm.complete(
            "You are the verification agent. Return the teaching answer only if it "
            "is supported by the evidence; otherwise replace unsupported parts with "
            "'not found'. Keep SOURCE_ID in the answer.\n"
            f"SOURCE_ID: {paper.source_id}\nEVIDENCE:\n{evidence}\nDRAFT:\n{draft}"
        )

    @staticmethod
    def _terms(text: str) -> list[str]:
        """Extract a few repeated content words for the UI."""
        words = re.findall(r"[A-Za-z][A-Za-z-]{5,}", text.lower())
        ignored = {"method", "results", "research", "using", "paper", "study"}
        counts: dict[str, int] = {}
        for word in words:
            if word not in ignored:
                counts[word] = counts.get(word, 0) + 1
        return [word for word, _ in sorted(counts.items(), key=lambda pair: -pair[1])[:8]]

    @staticmethod
    def _dot(problem: str, method: str, results: str) -> str:
        """Build a Graphviz flowchart from source-grounded summary fields."""
        def clean(value: str) -> str:
            """Escape a summary field for a Graphviz label."""
            return value.replace("\\", "").replace('"', "'").replace("\n", " ")[:180]

        return (
            "digraph paper { rankdir=LR; bgcolor='transparent'; "
            "node [shape=box, style='rounded,filled', fillcolor='#dbeafe', color='#2563eb']; "
            f'problem [label="Problem\\n{clean(problem)}"]; '
            f'method [label="Method\\n{clean(method)}"]; '
            f'results [label="Results\\n{clean(results)}"]; '
            "problem -> method -> results; }"
        )

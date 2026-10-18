"""LangGraph orchestration with a small fallback for offline development."""

import logging
from typing import Any, TypedDict

import requests

from agents.gap_finder import GapFinder
from agents.reader import Reader, Summary
from agents.searcher import Searcher
from agents.verifier import Verifier


class ResearchState(TypedDict, total=False):
    """State passed between research stages."""

    topic: str
    papers: list[Any]
    summaries: list[Any]
    gaps: list[Any]
    verifications: list[Any]
    error: str
    paper_errors: list[str]


class Orchestrator:
    """Run search, reading, gap finding, and verification in order."""

    def __init__(self, searcher: Searcher, reader: Reader, gap_finder: GapFinder, verifier: Verifier) -> None:
        """Store the pipeline's agents."""
        self.searcher = searcher
        self.reader = reader
        self.gap_finder = gap_finder
        self.verifier = verifier

    def run(self, topic: str, retries: int = 2) -> ResearchState:
        """Execute the pipeline and expose failures in the returned state."""
        state: ResearchState = {"topic": topic}
        logger = logging.getLogger(__name__)
        for attempt in range(retries + 1):
            try:
                state["papers"] = self.searcher.search(topic)
                state["summaries"] = []
                paper_errors: list[str] = []
                for paper in state["papers"]:
                    try:
                        state["summaries"].append(self.reader.read(paper))
                    except (OSError, ValueError, RuntimeError, requests.RequestException) as exc:
                        paper_errors.append(f"{paper.source_id}: {exc}")
                        state["summaries"].append(self._unavailable_summary(paper.source_id))
                usable_summaries = [
                    summary for summary in state["summaries"]
                    if summary.source_text != "not found"
                ]
                state["gaps"] = self.gap_finder.find(usable_summaries)
                state["verifications"] = self.verifier.verify_papers(state["papers"])
                if paper_errors:
                    state["paper_errors"] = paper_errors
                return state
            except Exception as exc:
                logger.warning("research attempt %d failed: %s", attempt + 1, exc)
                state["error"] = str(exc)
        return state

    @staticmethod
    def _unavailable_summary(source_id: str) -> Summary:
        """Create an explicit missing-source record without inventing content."""
        return Summary(
            source_id=source_id,
            problem="not found",
            method="not found",
            data="not found",
            results="not found",
            limitations="not found",
            source_text="not found",
        )

    def compile_langgraph(self) -> Any:
        """Compile an equivalent LangGraph when the optional package is installed."""
        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(ResearchState)
        graph.add_node("search", lambda state: {"papers": self.searcher.search(state["topic"])})
        graph.add_node("read", lambda state: {"summaries": [self.reader.read(p) for p in state["papers"]]})
        graph.add_node("gaps", lambda state: {"gaps": self.gap_finder.find(state["summaries"])})
        graph.add_node("verify", lambda state: {"verifications": self.verifier.verify_papers(state["papers"])})
        graph.add_edge(START, "search")
        graph.add_edge("search", "read")
        graph.add_edge("read", "gaps")
        graph.add_edge("gaps", "verify")
        graph.add_edge("verify", END)
        return graph.compile()

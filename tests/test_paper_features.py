"""Tests for paper quality and explanation helpers."""

from agents.paper_explainer import PaperExplainer
from agents.searcher import Paper


def test_quality_score_rewards_complete_metadata():
    """A paper with core metadata receives a non-zero transparent score."""
    paper = Paper(
        "paper:1", "A title", "An abstract", 2024, "10/example", None,
        "https://example.com/paper.pdf", "test", citation_count=40, venue="Journal",
    )
    assert paper.quality_score == 87


def test_flowchart_contains_source_stages():
    """The explanation graph always includes the three evidence stages."""
    dot = PaperExplainer._dot("problem", "method", "results")
    assert "problem" in dot
    assert "method" in dot
    assert "results" in dot

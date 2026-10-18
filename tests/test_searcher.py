"""Tests for search normalization."""

from agents.searcher import Paper, Searcher


def test_deduplicate_prefers_identity():
    """Duplicate DOI records collapse to one paper."""
    papers = [
        Paper("a", "A", "x", 2024, "10/test", None, None, "x"),
        Paper("b", "B", "y", 2023, "10/test", None, None, "y"),
    ]
    assert len(Searcher._deduplicate(papers)) == 1


def test_reconstruct_abstract():
    """OpenAlex inverted indexes become ordered text."""
    assert Searcher._reconstruct_abstract({"hello": [1], "world": [0]}) == "world hello"

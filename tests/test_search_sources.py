"""Tests for additional scholarly source normalization."""

from agents.searcher import Paper, Searcher


def test_recognized_venue_increases_quality_signal():
    """Recognized publisher metadata is visible in the quality score."""
    ieee = Paper("x", "Title", "Abstract", 2024, "10/x", None, "https://x", "crossref", venue="IEEE Transactions on AI")
    unknown = Paper("y", "Title", "Abstract", 2024, "10/y", None, "https://y", "crossref", venue="Unknown Journal")
    assert ieee.quality_score > unknown.quality_score


def test_crossref_jats_is_cleaned():
    """Crossref XML fragments do not leak into displayed abstracts."""
    assert Searcher._strip_jats("<jats:p>Hello</jats:p>") == "Hello"

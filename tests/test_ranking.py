"""Tests for explainable result ranking."""

from agents.searcher import Paper


def test_ranking_rewards_recent_cited_papers():
    """Recent, cited papers rank above sparse older records."""
    strong = Paper(
        "strong", "Title", "Abstract", 2025, "10/strong", None,
        "https://example.com", "crossref", citation_count=100, venue="IEEE Journal",
    )
    weak = Paper("weak", "Title", "Abstract", 2010, None, None, None, "arxiv")
    assert strong.ranking_score(current_year=2026) > weak.ranking_score(current_year=2026)

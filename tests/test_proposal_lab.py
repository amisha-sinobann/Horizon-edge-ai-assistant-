"""Tests for grounded proposal drafting."""

from agents.proposal_lab import ProposalLab
from agents.reader import Summary


def test_proposal_fallback_keeps_source_ids():
    """Offline proposal fallback remains explicitly source-linked."""
    summary = Summary("paper:1", "problem", "method", "data", "results", "limits", "source")
    proposal = ProposalLab(type("OfflineLLM", (), {"complete": lambda self, prompt: "not found"})()).draft(
        "robotics", [summary], []
    )
    assert proposal.source_ids == ["paper:1"]
    assert "robotics" in proposal.title

"""Tests for evaluation metrics."""

from eval.metrics import citation_verification_rate, source_coverage


def test_metrics():
    """Metrics report proportions."""
    assert citation_verification_rate([{"exists": True}, {"exists": False}]) == 0.5
    assert source_coverage([{"source_id": "paper:1"}]) == 1.0

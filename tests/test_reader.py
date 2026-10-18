"""Tests for summary parsing."""

from agents.reader import Reader


def test_parse_missing_fields_as_not_found():
    """Unspecified fields never receive fabricated values."""
    result = Reader._parse("problem: a\nmethod: b")
    assert result["problem"] == "a"
    assert result["results"] == "not found"

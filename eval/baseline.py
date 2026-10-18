"""Baseline runner for deterministic smoke evaluations."""


def baseline(topic: str) -> dict[str, str]:
    """Return a transparent no-LLM baseline result."""
    return {"topic": topic, "answer": "not found", "source_id": "not found"}

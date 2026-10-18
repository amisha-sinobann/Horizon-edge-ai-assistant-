"""Tests for natural-language request understanding."""

from core.query_understanding import QueryInterpreter


class StubLLM:
    """Return a deterministic response for interpreter tests."""

    def __init__(self, response: str) -> None:
        """Store the response."""
        self.response = response

    def complete(self, prompt: str) -> str:
        """Return the fixed test response."""
        return self.response


def test_llm_intent_is_normalized():
    """Valid JSON becomes a structured research intent."""
    interpreter = QueryInterpreter(StubLLM(
        '{"topic":"RAG evaluation","intent":"compare","subtopics":["faithfulness"],'
        '"constraints":["open access"],"year_from":2020,"year_to":2024,'
        '"requested_limit":8,"confidence":0.9}'
    ))
    result = interpreter.interpret("Compare open-access RAG evaluation papers")
    assert result.topic == "RAG evaluation"
    assert result.intent == "compare"
    assert result.requested_limit == 8
    assert result.method == "llm"


def test_heuristic_fallback_understands_gaps():
    """The application remains useful without an LLM key."""
    result = QueryInterpreter(StubLLM("not found")).interpret(
        "Find 6 papers on robotics open problems from 2020 to 2024"
    )
    assert result.intent == "gaps"
    assert result.requested_limit == 6
    assert result.year_from == 2020
    assert result.year_to == 2024

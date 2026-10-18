"""Command-line evaluation entry point."""

from eval.baseline import baseline


def run(topic: str) -> dict[str, str]:
    """Run the baseline evaluation."""
    return baseline(topic)


if __name__ == "__main__":
    import sys

    print(run(" ".join(sys.argv[1:]) or "not found"))

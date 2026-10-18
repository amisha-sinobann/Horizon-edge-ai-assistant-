"""Simple evaluation metrics."""


def citation_verification_rate(results: list[dict]) -> float:
    """Return the fraction of verification records that exist."""
    if not results:
        return 0.0
    return sum(bool(item.get("exists")) for item in results) / len(results)


def source_coverage(claims: list[dict]) -> float:
    """Return the fraction of claims carrying a source ID."""
    if not claims:
        return 0.0
    return sum(bool(item.get("source_id") or item.get("source_ids")) for item in claims) / len(claims)

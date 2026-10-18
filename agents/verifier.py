"""Citation and source-claim verification."""

from dataclasses import dataclass, asdict
from typing import Any

import requests

from agents.reader import Summary
from agents.searcher import Paper
from security.url_safety import UnsafeUrlError, validate_public_https_url


@dataclass
class Verification:
    """Verification result for one source or claim."""

    source_id: str
    exists: bool
    supported: bool
    flags: list[str]


class Verifier:
    """Verify paper identities and conservative claim support."""

    def verify_papers(self, papers: list[Paper]) -> list[Verification]:
        """Check DOI and arXiv-backed identities through public endpoints."""
        results: list[Verification] = []
        for paper in papers:
            if paper.doi:
                exists = self._head(f"https://doi.org/{paper.doi}")
            elif paper.arxiv_id:
                exists = self._head(f"https://export.arxiv.org/abs/{paper.arxiv_id}")
            else:
                exists = False
            results.append(Verification(
                source_id=paper.source_id,
                exists=exists,
                supported=exists,
                flags=[] if exists else ["paper identity not verified"],
            ))
        return results

    @staticmethod
    def verify_summaries(summaries: list[Summary]) -> list[Verification]:
        """Flag summaries whose source text is absent."""
        return [
            Verification(
                source_id=item.source_id,
                exists=item.source_text != "not found",
                supported=item.source_text != "not found",
                flags=[] if item.source_text != "not found" else ["source text not found"],
            )
            for item in summaries
        ]

    @staticmethod
    def _head(url: str) -> bool:
        """Return whether a public identity endpoint responds successfully."""
        try:
            validate_public_https_url(url)
            return requests.head(url, timeout=20, allow_redirects=False).ok
        except (requests.RequestException, UnsafeUrlError):
            return False

    @staticmethod
    def to_dicts(items: list[Verification]) -> list[dict[str, Any]]:
        """Convert verification records to dictionaries."""
        return [asdict(item) for item in items]

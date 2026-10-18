"""Scholarly search integrations."""

from dataclasses import asdict, dataclass
from datetime import datetime
import re
from typing import Any
import xml.etree.ElementTree as ET

import requests

from core.cache import JsonCache
from core.config import Settings


@dataclass
class Paper:
    """Normalized paper metadata from a scholarly provider."""

    source_id: str
    title: str
    abstract: str
    year: int | None
    doi: str | None
    arxiv_id: str | None
    url: str | None
    provider: str
    citation_count: int | None = None
    influential_citation_count: int | None = None
    venue: str | None = None

    @property
    def quality_score(self) -> int:
        """Return a transparent 0-100 metadata-quality score."""
        score = 0
        if self.title != "not found":
            score += 15
        if self.abstract != "not found":
            score += 20
        if self.year is not None:
            score += 15
        if self.doi or self.arxiv_id:
            score += 15
        if self.url:
            score += 10
        if self.venue:
            score += 10
            if self._recognized_venue:
                score += 5
        if self.citation_count is not None:
            score += min(15, round(self.citation_count / 20))
        return min(score, 100)

    def ranking_score(self, current_year: int | None = None) -> float:
        """Return an explainable relevance score for result ordering."""
        now = current_year or datetime.now().year
        recency = max(0.0, 1.0 - max(0, now - (self.year or now)) / 20)
        citations = min(1.0, (self.citation_count or 0) / 250)
        return round(self.quality_score * 0.55 + recency * 25 + citations * 20, 2)

    @property
    def _recognized_venue(self) -> bool:
        """Return whether venue metadata matches a recognized scholarly publisher."""
        venue = (self.venue or "").lower()
        signals = (
            "ieee", "acm", "nature", "springer", "elsevier", "cell press",
            "wiley", "oxford", "cambridge", "sage", "taylor & francis",
            "plos", "neurips", "aaai", "usenix", "jmlr",
        )
        return any(signal in venue for signal in signals)


class Searcher:
    """Search Semantic Scholar, OpenAlex, and arXiv with deduplication."""

    def __init__(self, settings: Settings, cache: JsonCache | None = None) -> None:
        """Initialize HTTP and disk-cache dependencies."""
        self.settings = settings
        self.cache = cache or JsonCache(settings.cache_dir)

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Fetch and cache a JSON response."""
        key = f"{url}?{sorted(params.items())}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        self.cache.set(key, payload)
        return payload

    def search(self, topic: str, limit: int | None = None) -> list[Paper]:
        """Search all providers, normalize results, and remove duplicates."""
        count = limit or self.settings.max_results
        papers: list[Paper] = []
        provider_errors: list[str] = []
        for provider, search in (
            ("Semantic Scholar", self._semantic_scholar),
            ("arXiv", self._arxiv),
            ("OpenAlex", self._openalex),
            ("Crossref", self._crossref),
            ("IEEE Xplore", self._ieee),
        ):
            if provider not in self.settings.enabled_sources:
                continue
            try:
                papers.extend(search(topic, count))
            except (requests.RequestException, TypeError, ValueError, KeyError, AttributeError) as exc:
                provider_errors.append(f"{provider}: {exc}")
        if not papers and provider_errors:
            raise RuntimeError(
                "All paper providers were unavailable. "
                + " | ".join(provider_errors)
            )
        return self._deduplicate(papers)[:count]

    def _semantic_scholar(self, topic: str, limit: int) -> list[Paper]:
        """Search Semantic Scholar."""
        headers = {"x-api-key": self.settings.semantic_scholar_api_key} if self.settings.semantic_scholar_api_key else {}
        response = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": topic, "limit": limit, "fields": "title,abstract,year,externalIds,openAccessPdf,url"},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        return [
            Paper(
                source_id=f"semantic:{item.get('paperId', item.get('title', 'not found'))}",
                title=item.get("title") or "not found",
                abstract=item.get("abstract") or "not found",
                year=item.get("year"),
                doi=(item.get("externalIds") or {}).get("DOI"),
                arxiv_id=(item.get("externalIds") or {}).get("ArXiv"),
                url=(item.get("openAccessPdf") or {}).get("url") or item.get("url"),
                provider="semantic_scholar",
                citation_count=item.get("citationCount"),
                influential_citation_count=item.get("influentialCitationCount"),
                venue=item.get("venue"),
            )
            for item in (result.get("data") or [])
            if isinstance(item, dict)
        ]

    def _openalex(self, topic: str, limit: int) -> list[Paper]:
        """Search OpenAlex."""
        params = {"search": topic, "per-page": limit}
        if self.settings.openalex_email:
            params["mailto"] = self.settings.openalex_email
        result = self._get("https://api.openalex.org/works", params)
        papers: list[Paper] = []
        for item in (result.get("results") or []):
            if not isinstance(item, dict):
                continue
            ids = item.get("ids") or {}
            primary_location = item.get("primary_location") or {}
            source = primary_location.get("source") or {}
            papers.append(Paper(
                source_id=f"openalex:{item.get('id', 'not found').split('/')[-1]}",
                title=item.get("title") or "not found",
                abstract=self._reconstruct_abstract(item.get("abstract_inverted_index")),
                year=item.get("publication_year"),
                doi=ids.get("doi", "").removeprefix("https://doi.org/") or None,
                arxiv_id=None,
                url=(item.get("open_access") or {}).get("oa_url") or item.get("doi"),
                provider="openalex",
                citation_count=item.get("cited_by_count"),
                venue=source.get("display_name"),
            ))
        return papers

    def _arxiv(self, topic: str, limit: int) -> list[Paper]:
        """Search arXiv's public Atom API."""
        url = "https://export.arxiv.org/api/query"
        params = {"search_query": f"all:{topic}", "start": 0, "max_results": limit}
        key = f"{url}?{sorted(params.items())}"
        cached = self.cache.get(key)
        if cached is None:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            cached = {"xml": response.text}
            self.cache.set(key, cached)
        root = ET.fromstring(cached["xml"])
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        papers: list[Paper] = []
        for entry in root.findall("atom:entry", namespace):
            identifier = (entry.findtext("atom:id", default="", namespaces=namespace)).rsplit("/", 1)[-1]
            title = " ".join((entry.findtext("atom:title", default="", namespaces=namespace)).split())
            abstract = " ".join((entry.findtext("atom:summary", default="", namespaces=namespace)).split())
            published = entry.findtext("atom:published", default="", namespaces=namespace)
            pdf_url = next(
                (
                    link.attrib.get("href")
                    for link in entry.findall("atom:link", namespace)
                    if link.attrib.get("type") == "application/pdf"
                ),
                None,
            )
            papers.append(Paper(
                source_id=f"arxiv:{identifier or 'not found'}",
                title=title or "not found",
                abstract=abstract or "not found",
                year=int(published[:4]) if published[:4].isdigit() else None,
                doi=None,
                arxiv_id=identifier or None,
                url=pdf_url,
                provider="arxiv",
                venue="arXiv",
            ))
        return papers

    def _crossref(self, topic: str, limit: int) -> list[Paper]:
        """Search Crossref's public scholarly works index."""
        params: dict[str, Any] = {
            "query.bibliographic": topic,
            "rows": limit,
            "select": "DOI,title,abstract,published,container-title,URL",
        }
        if self.settings.crossref_email:
            params["mailto"] = self.settings.crossref_email
        result = self._get("https://api.crossref.org/works", params)
        papers: list[Paper] = []
        for item in result.get("message", {}).get("items", []) or []:
            if not isinstance(item, dict):
                continue
            published = item.get("published", {}).get("date-parts", [[]])
            date_parts = published[0] if published else []
            title = (item.get("title") or ["not found"])[0]
            venue = (item.get("container-title") or ["not found"])[0]
            abstract = self._strip_jats(item.get("abstract") or "not found")
            doi = item.get("DOI")
            papers.append(Paper(
                source_id=f"crossref:{doi or title}",
                title=title or "not found",
                abstract=abstract,
                year=date_parts[0] if date_parts else None,
                doi=doi,
                arxiv_id=None,
                url=item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
                provider="crossref",
                venue=venue,
            ))
        return papers

    def _ieee(self, topic: str, limit: int) -> list[Paper]:
        """Search IEEE Xplore when an IEEE API key is configured."""
        if not self.settings.ieee_api_key:
            return []
        result = self._get(
            "https://ieeexploreapi.ieee.org/api/v1/search/articles",
            {"apikey": self.settings.ieee_api_key, "querytext": topic, "max_records": limit},
        )
        papers: list[Paper] = []
        for item in result.get("articles", []) or []:
            if not isinstance(item, dict):
                continue
            doi = item.get("doi")
            papers.append(Paper(
                source_id=f"ieee:{item.get('article_number') or doi or item.get('title', 'not found')}",
                title=item.get("title") or "not found",
                abstract=item.get("abstract") or "not found",
                year=item.get("publication_year"),
                doi=doi,
                arxiv_id=None,
                url=item.get("html_url") or item.get("pdf_url"),
                provider="ieee_xplore",
                citation_count=item.get("citing_paper_count"),
                venue=item.get("publication_title") or item.get("publication"),
            ))
        return papers

    @staticmethod
    def _strip_jats(text: str) -> str:
        """Remove simple JATS/XML tags from Crossref abstracts."""
        return re.sub(r"<[^>]+>", " ", text).replace("&nbsp;", " ").strip() or "not found"

    @staticmethod
    def _reconstruct_abstract(index: dict[str, list[int]] | None) -> str:
        """Reconstruct OpenAlex's inverted-index abstract representation."""
        if not index:
            return "not found"
        words = [(position, word) for word, positions in index.items() for position in positions]
        return " ".join(word for _, word in sorted(words)) or "not found"

    @staticmethod
    def _deduplicate(papers: list[Paper]) -> list[Paper]:
        """Deduplicate by DOI, arXiv ID, or normalized title."""
        seen: set[str] = set()
        unique: list[Paper] = []
        for paper in papers:
            identity = (paper.doi or paper.arxiv_id or paper.title).lower().strip()
            if identity and identity not in seen:
                seen.add(identity)
                unique.append(paper)
        return unique

    @staticmethod
    def to_dicts(papers: list[Paper]) -> list[dict[str, Any]]:
        """Convert paper records to serializable dictionaries."""
        return [asdict(paper) for paper in papers]

"""Open-access PDF extraction and source-grounded summaries."""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests

from agents.searcher import Paper
from core.llm import LLMClient
from security.url_safety import validate_pdf_response, validate_public_https_url


@dataclass
class Summary:
    """Structured summary linked to one paper source ID."""

    source_id: str
    problem: str
    method: str
    data: str
    results: str
    limitations: str
    source_text: str


class Reader:
    """Download open PDFs and produce structured summaries."""

    def __init__(
        self,
        llm: LLMClient,
        paper_dir: str | Path = "data/papers",
        max_pdf_bytes: int = 25 * 1024 * 1024,
    ) -> None:
        """Initialize the model and local PDF directory."""
        self.llm = llm
        self.paper_dir = Path(paper_dir)
        self.paper_dir.mkdir(parents=True, exist_ok=True)
        self.max_pdf_bytes = max_pdf_bytes

    def extract_text(self, pdf_path: str | Path) -> str:
        """Extract text from a PDF using PyMuPDF."""
        import fitz

        document = fitz.open(pdf_path)
        return "\n".join(page.get_text() for page in document)

    def read(self, paper: Paper) -> Summary:
        """Download and summarize a paper, returning ``not found`` on missing data."""
        if not paper.url:
            text = paper.abstract
        else:
            path = self.paper_dir / f"{paper.source_id.replace(':', '_')}.pdf"
            if not path.exists():
                validate_public_https_url(paper.url)
                response = requests.get(paper.url, timeout=60, allow_redirects=False, stream=True)
                response.raise_for_status()
                content_length = int(response.headers.get("content-length", "0") or 0)
                if content_length > self.max_pdf_bytes:
                    raise ValueError("PDF exceeds configured maximum size")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    size += len(chunk)
                    if size > self.max_pdf_bytes:
                        raise ValueError("PDF exceeds configured maximum size")
                    chunks.append(chunk)
                content = b"".join(chunks)
                validate_pdf_response(
                    response.headers.get("content-type", ""),
                    content[:5],
                    len(content),
                    self.max_pdf_bytes,
                )
                path.write_bytes(content)
            text = self.extract_text(path)
        prompt = (
            "Summarize only the source text below. Return exactly five lines labeled "
            "problem, method, data, results, limitations. Use 'not found' when absent.\n\n"
            f"SOURCE_ID: {paper.source_id}\n{text[:30000]}"
        )
        parsed = self._parse(self.llm.complete(prompt))
        if all(value == "not found" for value in parsed.values()):
            parsed = self._heuristic_summary(text)
        return Summary(source_id=paper.source_id, source_text=text, **parsed)

    @staticmethod
    def _parse(response: str) -> dict[str, str]:
        """Parse labeled model output without fabricating missing fields."""
        values = {key: "not found" for key in ("problem", "method", "data", "results", "limitations")}
        for line in response.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                if key.strip().lower() in values and value.strip():
                    values[key.strip().lower()] = value.strip()
        return values

    @staticmethod
    def _heuristic_summary(text: str) -> dict[str, str]:
        """Create a conservative summary from source sentences without an LLM."""
        sentences = [part.strip() for part in text.replace("\n", " ").split(".") if part.strip()]
        if not sentences:
            return {key: "not found" for key in ("problem", "method", "data", "results", "limitations")}
        joined = ". ".join(sentences)
        def find(keywords: tuple[str, ...], default: str) -> str:
            """Find the first source sentence containing one of the keywords."""
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in keywords):
                    return sentence[:500]
            return default
        return {
            "problem": find(("problem", "challenge", "aim", "goal", "address"), sentences[0][:500]),
            "method": find(("method", "propose", "approach", "framework", "model", "algorithm"), "not found"),
            "data": find(("dataset", "data", "benchmark", "experiment"), "not found"),
            "results": find(("result", "improve", "achieve", "outperform", "show"), "not found"),
            "limitations": find(("limit", "however", "future work", "remain"), "not found"),
        }

    @staticmethod
    def to_dict(summary: Summary) -> dict[str, Any]:
        """Convert a summary to a serializable dictionary."""
        return asdict(summary)

"""Environment-backed application configuration."""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Tuple

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    provider: str = "gemini"
    model: str = "gemini-1.5-flash"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    semantic_scholar_api_key: str = ""
    openalex_email: str = ""
    ieee_api_key: str = ""
    crossref_email: str = ""
    cache_dir: Path = Path("data/cache")
    max_results: int = 20
    enabled_sources: Tuple[str, ...] = (
        "Semantic Scholar", "arXiv", "OpenAlex", "Crossref", "IEEE Xplore"
    )


def load_settings(dotenv_path: str | Path | None = None) -> Settings:
    """Load settings from an optional dotenv file and process environment."""
    load_dotenv(dotenv_path)
    return Settings(
        provider=os.getenv("LLM_PROVIDER", "gemini").lower(),
        model=os.getenv("LLM_MODEL", "gemini-1.5-flash"),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY", ""),
        openalex_email=os.getenv("OPENALEX_EMAIL", ""),
        ieee_api_key=os.getenv("IEEE_API_KEY", ""),
        crossref_email=os.getenv("CROSSREF_EMAIL", os.getenv("OPENALEX_EMAIL", "")),
        cache_dir=Path(os.getenv("HF_CACHE_DIR", "data/cache")),
        max_results=int(os.getenv("HF_MAX_RESULTS", "20")),
        enabled_sources=tuple(
            value.strip() for value in os.getenv(
                "HF_SOURCES",
                "Semantic Scholar,arXiv,OpenAlex,Crossref,IEEE Xplore",
            ).split(",") if value.strip()
        ),
    )

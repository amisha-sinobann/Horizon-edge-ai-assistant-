# HorizonForge Specification

## Project goal

HorizonForge takes a research topic and returns:

- Relevant papers
- A summary of each paper
- A list of research gaps
- A verified citation list

A Verifier agent checks every claim against the source paper so the output has
no hallucinated references.

## Agents

1. **Searcher**: Finds papers using the Semantic Scholar, arXiv, and OpenAlex
   APIs. Removes duplicates and ranks results by relevance and recency.
2. **Reader**: Downloads open-access PDFs, extracts text with PyMuPDF, and
   writes a structured summary containing the problem, method, data, results,
   and limitations.
3. **Gap Finder**: Compares the summaries and proposes research gaps, each with
   the papers that support it.
4. **Verifier**: Checks that every cited paper exists by DOI or arXiv ID and
   that each claim is supported by the source text. Flags unsupported claims.
5. **Orchestrator**: Runs the agents in order using LangGraph, handling errors,
   retries, and logging.

## Tech stack

- Python 3.11
- LangGraph for orchestration
- A provider-agnostic, configuration-driven LLM wrapper supporting Gemini,
  OpenAI, Anthropic, or Ollama
- Gemini free tier as the default LLM provider
- API keys loaded from a `.env` file
- ChromaDB for vector search
- PyMuPDF for PDF processing
- Streamlit for the demo UI
- pytest for tests

## Rules

- Never invent papers, DOIs, citations, or numbers. If data is missing, return
  `"not found"`.
- Every output claim must carry a source ID.
- Cache all API responses on disk to save rate limits.
- Add type hints and docstrings to every function.
- Keep secrets only in `.env`; commit a `.env.example` file.
- Keep each agent in its own file with its own tests.

## Folder structure

```text
horizonforge/
  agents/ (searcher.py, reader.py, gap_finder.py, verifier.py)
  core/ (llm.py, config.py, cache.py, graph.py)
  eval/ (baseline.py, run_eval.py, metrics.py)
  app/ (streamlit_app.py)
  tests/
  data/
  SPEC.md
  README.md
  requirements.txt
  .env.example
```

## Task checklist

- [x] Define configuration and environment-variable handling.
- [x] Implement disk caching for external API responses.
- [x] Implement the Searcher agent and source integrations.
- [x] Implement the Reader agent and PDF extraction.
- [x] Implement the Gap Finder agent.
- [x] Implement the Verifier agent and source-backed claim checks.
- [x] Implement the LangGraph orchestrator with retries, errors, and logging.
- [x] Add the provider-agnostic LLM wrapper.
- [x] Add the Streamlit demo UI.
- [x] Add evaluation baselines, metrics, and runner.
- [x] Add focused tests for every agent and core module.
- [x] Add documentation, dependency declarations, and environment examples.

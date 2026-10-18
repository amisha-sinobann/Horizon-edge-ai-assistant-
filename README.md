# HorizonForge

HorizonForge is a source-grounded, multi-agent research assistant. Given a
research topic, it searches scholarly indexes, reads open-access papers,
identifies research gaps, and verifies citations and claims against source
text.

## Quick start

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app/streamlit_app.py
```

The default provider is Gemini. Set `LLM_PROVIDER` and the corresponding key
in `.env` to use another supported provider. Search APIs remain usable without
an LLM key; summaries then report `not found` rather than inventing content.

## User interface

The Streamlit Research Desk provides:

- A plain-language research question box and paper-count control
- Readable paper cards with source IDs, abstracts, links, and structured summaries
- Separate tabs for papers, research gaps, citation verification, and export
- A JSON report download that excludes full extracted PDF text
- Safe error messages and a button to clear the current report
- A calm light theme configured in `.streamlit/config.toml`
- Natural-language request understanding that extracts the research topic,
  task type, constraints, date range, and requested paper count
- Scholarly search across Semantic Scholar, arXiv, OpenAlex, Crossref, and
  optional IEEE Xplore API access
- Provider directory covering PubMed/MEDLINE, Europe PMC, ACM Digital Library,
  DBLP, CORE, DOAJ, OpenCitations, Dimensions, Web of Science, and Scopus,
  with active/optional/planned status shown transparently in the UI
- Venue metadata and recognized-publisher signals for IEEE, ACM, Nature,
  Springer, Elsevier, Wiley, NeurIPS, AAAI, and related sources
- 20–50 paper search control with transparent metadata quality scores
- A paper explainer that renders a problem → method → results flowchart
- Interactive Plotly evidence pipeline, section-coverage radar, and concept network
- Deterministic abstract-based visual explanations when no LLM key is configured
- An evidence provenance graph connecting papers to extracted evidence and gaps
- Proposal Lab for source-linked research questions, hypotheses, methods, risks,
  and evaluation plans
- A grounded paper tutor that answers questions only from the selected paper

Run it from the repository root:

```powershell
streamlit run app/streamlit_app.py
```

## Layout

`agents/` contains the independent research stages, `core/` contains shared
configuration and orchestration, `eval/` contains lightweight evaluation
helpers, and `tests/` contains unit tests.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full research methodology,
agent contracts, provenance model, ranking formula, security boundaries,
runtime state contracts, resilience behavior, reproducibility guidance,
limitations, and a suggested thesis evaluation plan.

## Detailed research lifecycle

1. **Frame the question:** the NLP interpreter extracts intent, subtopics,
   constraints, date range, and requested paper count.
2. **Search broadly:** enabled scholarly providers are queried independently;
   cached responses reduce rate-limit pressure.
3. **Normalize evidence:** provider-specific records become one paper schema and
   duplicates are removed using DOI, arXiv ID, or normalized title.
4. **Prioritize transparently:** metadata completeness, recency, citations,
   venue signals, and availability determine inspection order.
5. **Read safely:** only validated, bounded PDF downloads are parsed. Missing or
   inaccessible source text remains `not found`.
6. **Synthesize cautiously:** gaps and proposal ideas are generated only from
   summaries with source text and retain their supporting source IDs.
7. **Verify and export:** identity checks, evidence status, provenance links, and
   JSON/CSV/BibTeX exports make the report suitable for review.

## Safety guarantees

- Missing data is represented as `not found`.
- Paper identity comes only from API responses.
- Claims and gaps carry source IDs.
- External JSON responses are cached under `data/cache/`.
- Secrets are loaded from `.env` and are never required in source files.
# horizen edge

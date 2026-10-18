# HorizonForge architecture and research methodology

## 1. Research workflow

HorizonForge separates discovery, interpretation, source reading, synthesis,
verification, and presentation. A run follows this sequence:

1. **Query understanding** converts a natural-language request into a research
   brief: topic, intent, subtopics, constraints, date range, and result count.
2. **Multi-source discovery** queries Semantic Scholar, arXiv, OpenAlex,
   Crossref, and optionally IEEE Xplore.
3. **Normalization and deduplication** converts provider-specific records into
   one `Paper` model and deduplicates by DOI, arXiv ID, or normalized title.
4. **Ranking** combines metadata completeness, recency, citations, venue
   metadata, and open-source availability. The score is explainable and is not
   presented as peer-review quality.
5. **Source reading** downloads bounded open-access PDFs, extracts text with
   PyMuPDF, and creates a structured summary.
6. **Gap synthesis** compares only summaries with available source text. Every
   gap retains the IDs of supporting papers.
7. **Verification** checks DOI/arXiv identity endpoints and flags missing or
   unsupported records.
8. **Presentation** exposes papers, evidence, provenance graphs, comparisons,
   visual explanations, a paper tutor, and a proposal draft.

## 2. Agent responsibilities

| Agent | Input | Output | Safety boundary |
|---|---|---|---|
| Query Interpreter | User request | Structured intent | Uses `not found` for absent constraints |
| Searcher | Topic and filters | Normalized papers | Provider failures are isolated |
| Reader | Paper metadata and PDF | Structured summary | Size, URL, signature, and source checks |
| Gap Finder | Source-backed summaries | Linked research gaps | Cannot cite unknown source IDs |
| Verifier | Paper identities and summaries | Verification flags | Unsupported claims are flagged |
| Paper Explainer | One paper and summary | Charts and visual explanation | Uses source text only |
| Proposal Lab | Summaries and gaps | Research concept draft | Every draft carries source IDs |
| Orchestrator | User topic | Complete research state | Retries pipeline failures and isolates paper failures |

## 3. Evidence and provenance model

Every paper receives a stable `source_id`. Summaries, gaps, verification
records, visual explanations, tutor responses, and proposal sections reference
that ID. The provenance graph represents:

```text
paper -> extracted evidence -> synthesis/gap -> proposal concept
```

An absent abstract, PDF, DOI, claim, or metric is represented as `not found`.
The system never fills missing scholarly facts with generated guesses.

## 4. Ranking methodology

The ranking score is an engineering prioritization signal:

- Metadata completeness: title, abstract, year, identifier, source link
- Venue metadata and recognized publisher signal
- Recency relative to the current year
- Citation count when supplied by the provider

The score helps users decide what to inspect first. It must not be interpreted
as scientific validity, journal impact, peer-review quality, or evidence that a
paper is correct.

The current implementation uses the following transparent calculation:

```text
quality = metadata completeness score, capped at 100
recency = max(0, 1 - years_since_publication / 20)
citations = min(1, citation_count / 250)
ranking = 0.55 * quality + 25 * recency + 20 * citations
```

The quality score rewards a title, abstract, year, DOI or arXiv identifier,
source URL, venue, recognized publisher signal, and citation metadata. Missing
metadata lowers confidence in prioritization; it does not prove that a paper
is poor research.

## 5. Runtime state and data contracts

The orchestrator passes a typed research state through the pipeline:

| Field | Meaning | Failure representation |
|---|---|---|
| `topic` | Normalized research request | Original user text |
| `papers` | Deduplicated `Paper` records | Empty list plus provider error |
| `summaries` | Structured problem/method/data/results/limitations | Fields set to `not found` |
| `gaps` | Cross-paper, source-linked gap records | Empty list when evidence is insufficient |
| `verifications` | DOI/arXiv identity and claim checks | Explicit verification flags |
| `paper_errors` | Per-paper reader failures | Source ID plus error description |
| `error` | Pipeline-level failure after retries | Error message, never a fake report |

Each agent has a narrow responsibility. Search providers can fail
independently, while a failed PDF is isolated to that paper. Gap synthesis
receives only summaries with extracted source text, preventing unavailable
documents from influencing research conclusions.

## 6. Execution and resilience

1. The query interpreter extracts topic, intent, constraints, year range, and
   requested result count.
2. The searcher calls enabled providers, reads cached responses first, and
   normalizes records into a common schema.
3. Deduplication prefers DOI and arXiv identifiers, then falls back to a
   normalized title.
4. The reader validates outbound URLs and bounded PDF downloads before parsing.
5. The gap finder and proposal tools receive only known source IDs.
6. The verifier runs after synthesis so identity and support status are visible
   beside the final report.
7. The UI exposes partial failures instead of hiding them behind a success
   message.

The imperative runner retries the full pipeline twice after a pipeline-level
exception. It does not retry indefinitely, and it does not discard successful
partial results when an individual paper cannot be read.

## 7. Security controls

- Credential-free HTTPS is required for outbound paper and DOI requests.
- DNS results resolving to private, loopback, link-local, reserved, multicast,
  or unspecified addresses are rejected.
- Redirects are not followed automatically.
- PDFs are streamed with a size limit, PDF signature check, and content-type
  validation.
- Provider failures and oversized/malformed papers do not abort unrelated work.
- Secrets are loaded from `.env`, while `.env.example` documents configuration.

## 8. Reproducibility and observability

- Provider JSON responses are cached on disk to reduce rate-limit pressure and
  make repeated runs more comparable.
- The enabled provider set, year range, open-access preference, and result
  limit are recorded in the active session configuration.
- Every displayed paper, summary, gap, and proposal section can be traced to a
  stable source ID.
- JSON, CSV, and BibTeX exports support downstream analysis and supervisor
  review.
- The session history records completed topics, interpreted intent, and result
  counts without storing secrets.
- Provider and paper-level errors remain visible so a result can be audited
  rather than mistaken for complete coverage.

## 9. Known limitations and research extensions

- Citation counts and venue metadata vary by provider and may be incomplete.
- OpenAlex, Crossref, and preprint records can have limited abstracts.
- Proposal Lab produces a planning draft, not a claim of novelty or a
  substitute for supervisor review.
- Future research extensions include claim-level entailment benchmarks,
  author/institution disambiguation, citation-context analysis, temporal
  knowledge graphs, and human evaluation of gap quality.

## 10. Suggested thesis evaluation

Evaluate HorizonForge against a manually curated benchmark using:

- Search recall@k and duplicate-removal accuracy
- Citation identity precision and recall
- Summary factuality judged against source passages
- Claim source-coverage rate
- Gap usefulness rated by domain experts
- Time-to-first-relevant-paper and user task completion
- Ablations for provider count, caching, verifier, and query interpretation

For a stronger dissertation study, report confidence intervals across multiple
topics, compare against a single-provider baseline and a general-purpose LLM,
and include an error taxonomy covering missing metadata, inaccessible PDFs,
incorrect identity matches, unsupported claims, and irrelevant gaps.

"""Friendly Streamlit workspace for HorizonForge research runs."""

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import streamlit as st

# Streamlit adds the script directory to the import path, not always the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.gap_finder import GapFinder
from agents.reader import Reader
from agents.paper_explainer import PaperExplainer
from agents.proposal_lab import ProposalLab
from agents.searcher import Searcher
from agents.verifier import Verifier
from core.cache import JsonCache
from core.config import load_settings
from core.graph import Orchestrator
from core.llm import LLMClient
from core.query_understanding import QueryInterpreter, ResearchIntent


st.set_page_config(
    page_title="HorizonForge Research Desk",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { max-width: 1200px; padding-top: 2rem; }
    .hero { padding: 1.5rem 1.75rem; border-radius: 1rem;
            background: linear-gradient(120deg, #172554, #1e3a8a);
            color: white; margin-bottom: 1.25rem; }
    .source-id { color: #64748b; font-size: 0.82rem; }
    .flow-row { display: flex; align-items: stretch; gap: .55rem; overflow-x: auto;
                padding: .5rem 0 1rem; }
    .flow-card { min-width: 190px; max-width: 250px; padding: 1rem;
                 border: 1px solid #93c5fd; border-radius: .8rem;
                 background: linear-gradient(145deg, #eff6ff, #dbeafe);
                 color: #0f172a; box-shadow: 0 5px 14px #0f172a18; }
    .flow-label { font-weight: 700; color: #1d4ed8; margin-bottom: .45rem; }
    .flow-value { font-size: .9rem; line-height: 1.35; }
    .flow-arrow { align-self: center; color: #2563eb; font-size: 1.7rem; font-weight: 700; }
    .flow-note { color: #64748b; font-size: .82rem; }
    .metric-card { padding: .9rem 1rem; border-radius: .8rem; background: #f8fafc;
                   border: 1px solid #e2e8f0; }
    .eyebrow { color: #64748b; text-transform: uppercase; letter-spacing: .08em;
               font-size: .72rem; font-weight: 700; }
    .hint { color: #475569; font-size: .9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _records(value: list[Any], include_source_text: bool = False) -> list[dict[str, Any]]:
    """Convert dataclass results to JSON-safe dictionaries."""
    records = [asdict(item) for item in value]
    if not include_source_text:
        for record in records:
            record.pop("source_text", None)
    for record, item in zip(records, value):
        if hasattr(item, "quality_score"):
            record["quality_score"] = item.quality_score
    return records


def _bibtex(paper: Any) -> str:
    """Create a conservative BibTeX record from verified metadata."""
    cite_key = "".join(character for character in paper.source_id if character.isalnum())[:32] or "paper"
    authors = "not found"
    year = paper.year or "not found"
    venue = paper.venue or "not found"
    identifier = paper.doi or paper.arxiv_id or "not found"
    return (
        f"@article{{{cite_key},\n"
        f"  title = {{{paper.title}}},\n"
        f"  author = {{{authors}}},\n"
        f"  year = {{{year}}},\n"
        f"  journal = {{{venue}}},\n"
        f"  doi = {{{identifier}}},\n"
        f"  url = {{{paper.url or 'not found'}}}\n"
        "}\n"
    )


def _paper_csv(papers: list[Any]) -> str:
    """Serialize paper metadata as CSV for spreadsheet workflows."""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["title", "source_id", "provider", "venue", "year", "quality_score", "citations", "url"])
    for paper in papers:
        writer.writerow([
            paper.title, paper.source_id, paper.provider, paper.venue or "not found",
            paper.year or "not found", paper.quality_score,
            paper.citation_count if paper.citation_count is not None else "not found",
            paper.url or "not found",
        ])
    return output.getvalue()


def _ranking_explanation(paper: Any) -> str:
    """Describe the signals behind a paper's ranking score."""
    return (
        f"Ranking score: **{paper.ranking_score():.1f}**  \n"
        f"Signals — metadata: {paper.quality_score}/100 · "
        f"year: {paper.year or 'not found'} · "
        f"citations: {paper.citation_count if paper.citation_count is not None else 'not found'} · "
        f"venue: {paper.venue or 'not found'}"
    )


def _show_provider_directory() -> None:
    """Show the scholarly provider ecosystem and current integration status."""
    providers = [
        ("Semantic Scholar", "Active", "AI-powered scholarly search and citation graph"),
        ("arXiv", "Active", "Open research preprints in science and engineering"),
        ("OpenAlex", "Active", "Open catalog of works, authors, institutions, and venues"),
        ("Crossref", "Active", "DOI and publisher metadata across scholarly literature"),
        ("IEEE Xplore", "Optional API key", "Engineering, computing, and electronics literature"),
        ("PubMed / MEDLINE", "Planned", "Biomedical and life-sciences literature"),
        ("Europe PMC", "Planned", "Open biomedical abstracts and full-text links"),
        ("ACM Digital Library", "Planned", "Computing and information technology research"),
        ("DBLP", "Planned", "Computer science bibliography and publication metadata"),
        ("CORE", "Planned", "Open-access full-text research aggregation"),
        ("DOAJ", "Planned", "Directory of open-access journals and articles"),
        ("OpenCitations", "Planned", "Open citation and bibliographic graph data"),
        ("Dimensions", "Planned", "Research outputs, citations, grants, and analytics"),
        ("Web of Science", "Planned", "Curated citation index for institutional access"),
        ("Scopus", "Planned", "Abstract and citation database for institutional access"),
    ]
    st.dataframe(
        [{"Provider": name, "Status": status, "Coverage": coverage} for name, status, coverage in providers],
        width="stretch",
        hide_index=True,
    )


def _show_methodology() -> None:
    """Explain the research pipeline in the user interface."""
    st.markdown(
        """
        **HorizonForge is an evidence pipeline, not a generic chatbot.**

        1. **Understand** — converts your request into a structured research brief.
        2. **Discover** — searches multiple scholarly indexes and removes duplicates.
        3. **Prioritize** — ranks papers using transparent metadata, recency, venue,
           citation, and availability signals.
        4. **Read** — extracts open-access source text and creates a structured summary.
        5. **Synthesize** — identifies gaps only from summaries that have source evidence.
        6. **Verify** — checks identifiers and flags unsupported or unavailable evidence.
        7. **Explain** — generates charts, provenance links, comparisons, and proposal drafts.

        Missing information is shown as **`not found`**. A quality/ranking score is
        only a prioritization aid; it is not a peer-review or scientific-validity score.
        """
    )
    st.markdown("**What each score means**")
    st.caption(
        "Quality measures metadata completeness. Ranking combines quality, recency, "
        "citation count, and venue signals. Neither score measures truth, novelty, "
        "peer-review quality, or research impact."
    )
    st.markdown("**Failure behavior**")
    st.caption(
        "A provider can fail without stopping other providers. An unsafe, oversized, "
        "or unreadable PDF becomes an explicit `not found` record, while usable papers "
        "continue through gap finding and verification."
    )
    st.markdown("**Audit trail**")
    st.caption(
        "Stable source IDs connect papers to summaries, extracted evidence, gaps, "
        "visual explanations, tutor answers, and proposal sections. Use JSON or CSV "
        "export when you need a reproducible review record."
    )


def _build_orchestrator(limit: int) -> Orchestrator:
    """Construct the configured research pipeline for one run."""
    settings = load_settings()
    settings = _set_enabled_sources(settings)
    settings = settings.__class__(**{**settings.__dict__, "max_results": limit})
    llm = LLMClient(settings)
    return Orchestrator(
        Searcher(settings, JsonCache(settings.cache_dir)),
        Reader(llm),
        GapFinder(llm),
        Verifier(),
    )


def _understand_request(query: str, limit: int) -> tuple[ResearchIntent, Orchestrator]:
    """Understand a user request and build the matching research pipeline."""
    settings = load_settings()
    settings = _set_enabled_sources(settings)
    llm = LLMClient(settings)
    intent = QueryInterpreter(llm).interpret(query)
    effective_limit = intent.requested_limit or limit
    settings = settings.__class__(**{**settings.__dict__, "max_results": effective_limit})
    return intent, Orchestrator(
        Searcher(settings, JsonCache(settings.cache_dir)),
        Reader(llm),
        GapFinder(llm),
        Verifier(),
    )


def _set_enabled_sources(settings: Any) -> Any:
    """Apply source selections from the sidebar to runtime settings."""
    selected = st.session_state.get("enabled_sources")
    if selected:
        return settings.__class__(**{**settings.__dict__, "enabled_sources": tuple(selected)})
    return settings


def _show_paper_card(paper: Any, summary: Any | None) -> None:
    """Render one paper and its source-grounded summary."""
    year = paper.year if paper.year is not None else "not found"
    with st.container(border=True):
        st.markdown(f"#### {paper.title}")
        st.markdown(f'<span class="source-id">{paper.source_id} · {paper.provider} · {year}</span>', unsafe_allow_html=True)
        quality = paper.quality_score
        st.progress(quality / 100, text=f"Metadata quality: {quality}/100")
        st.caption(_ranking_explanation(paper))
        quality_notes = ["title", "abstract", "year", "identifier", "source link"]
        if paper.venue:
            quality_notes.append("venue")
        if paper._recognized_venue:
            st.caption(f"🏛️ Recognized venue signal: {paper.venue}")
        elif paper.venue:
            st.caption(f"Journal/conference: {paper.venue}")
        st.caption("Quality is a transparent metadata score, not a peer-review judgment. "
                   "Available signals: " + ", ".join(quality_notes))
        if paper.doi:
            st.caption(f"DOI: {paper.doi}")
        if paper.url:
            st.link_button("Open source", paper.url)
        st.write(paper.abstract)
        if summary:
            with st.expander("Structured summary"):
                columns = st.columns(2)
                fields = ("problem", "method", "data", "results", "limitations")
                for index, field in enumerate(fields):
                    columns[index % 2].markdown(f"**{field.title()}**  \n{getattr(summary, field)}")


def _show_result_metrics(papers: list[Any], summaries: dict[str, Any], verifications: list[Any]) -> None:
    """Render a compact dashboard summary for a completed run."""
    verified = sum(item.exists and item.supported for item in verifications)
    summarized = sum(item.source_id in summaries for item in papers)
    venues = sum(bool(item.venue) for item in papers)
    average_quality = round(sum(item.quality_score for item in papers) / len(papers)) if papers else 0
    columns = st.columns(4)
    values = [
        ("Papers found", len(papers), "Across scholarly indexes"),
        ("Avg. metadata score", f"{average_quality}/100", "Not a peer-review verdict"),
        ("Summaries ready", f"{summarized}/{len(papers)}", "Source-linked analysis"),
        ("Verified identities", f"{verified}/{len(verifications)}", f"{venues} with venue metadata"),
    ]
    for column, (label, value, caption) in zip(columns, values):
        with column:
            st.markdown(f'<div class="metric-card"><div class="eyebrow">{label}</div>'
                        f'<h3>{value}</h3><div class="hint">{caption}</div></div>',
                        unsafe_allow_html=True)


def _show_visual_explanation(explanation: Any) -> None:
    """Render detailed interactive pipeline, radar, and concept-network charts."""
    import plotly.graph_objects as go

    stage_names = [label for label, _ in explanation.stages]
    stage_values = [value for _, value in explanation.stages]
    pipeline = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                pad=30,
                thickness=28,
                label=stage_names,
                color=["#2563eb", "#7c3aed", "#059669", "#ea580c"],
                customdata=stage_values,
                hovertemplate="<b>%{label}</b><br>%{customdata}<extra></extra>",
            ),
            link=dict(
                source=list(range(len(stage_names) - 1)),
                target=list(range(1, len(stage_names))),
                value=[1] * (len(stage_names) - 1),
                color="rgba(37,99,235,.25)",
            ),
        )
    )
    pipeline.update_layout(
        title="Evidence pipeline: source → analysis → outcome",
        height=340,
        margin=dict(l=10, r=10, t=55, b=10),
        font=dict(size=13),
    )
    st.plotly_chart(pipeline, width="stretch", key=f"pipeline-{explanation.source_id}")

    left, right = st.columns(2)
    with left:
        radar = go.Figure(
            go.Scatterpolar(
                r=explanation.stage_scores + [explanation.stage_scores[0]],
                theta=stage_names + [stage_names[0]],
                fill="toself",
                line_color="#2563eb",
                fillcolor="rgba(37,99,235,.25)",
                hovertemplate="%{theta}: %{r}/100<extra></extra>",
            )
        )
        radar.update_layout(
            title="Evidence coverage by section",
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            height=380,
            margin=dict(l=35, r=35, t=55, b=25),
        )
        st.plotly_chart(radar, width="stretch", key=f"radar-{explanation.source_id}")
    with right:
        terms = explanation.key_terms
        positions = {term: (index % 2, -(index // 2)) for index, term in enumerate(terms)}
        network = go.Figure()
        for start, end, weight in explanation.concept_links:
            x0, y0 = positions[start]
            x1, y1 = positions[end]
            network.add_trace(go.Scatter(
                x=[x0, x1, None], y=[y0, y1, None],
                mode="lines", line=dict(width=weight / 2, color="#93c5fd"),
                hoverinfo="skip", showlegend=False,
            ))
        network.add_trace(go.Scatter(
            x=[positions[term][0] for term in terms],
            y=[positions[term][1] for term in terms],
            mode="markers+text",
            text=terms,
            textposition="top center",
            marker=dict(size=22, color="#2563eb", line=dict(width=2, color="white")),
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        ))
        network.update_layout(
            title="Concept network extracted from source",
            height=380,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=10, r=10, t=55, b=10),
            plot_bgcolor="white",
        )
        st.plotly_chart(network, width="stretch", key=f"network-{explanation.source_id}")

    st.markdown("#### Source-backed explanation")
    for label, value in explanation.stages:
        with st.expander(label, expanded=label in {"Problem", "Method"}):
            st.write(value)
            st.caption(f"Evidence coverage score: {explanation.stage_scores[stage_names.index(label)]}/100 · {explanation.source_id}")


def _show_evidence_graph(papers: list[Any], summaries: dict[str, Any], gaps: list[Any]) -> None:
    """Render a provenance graph connecting papers, evidence, and research gaps."""
    import plotly.graph_objects as go

    nodes: list[tuple[str, str, str]] = []
    edges: list[tuple[int, int]] = []
    for paper in papers:
        paper_index = len(nodes)
        nodes.append((paper.source_id, "paper", paper.title[:42]))
        summary = summaries.get(paper.source_id)
        if summary:
            for field in ("problem", "method", "results", "limitations"):
                if getattr(summary, field) != "not found":
                    evidence_index = len(nodes)
                    nodes.append((f"{paper.source_id}:{field}", "evidence", field.title()))
                    edges.append((paper_index, evidence_index))
    for gap in gaps:
        gap_index = len(nodes)
        nodes.append((f"gap:{gap_index}", "gap", gap.claim[:42]))
        for source_id in gap.source_ids:
            source_index = next((i for i, node in enumerate(nodes) if node[0] == source_id), None)
            if source_index is not None:
                edges.append((source_index, gap_index))
    if not nodes:
        st.info("No provenance records are available yet.")
        return
    import math
    positions = {
        index: (math.cos(index * 2 * math.pi / len(nodes)), math.sin(index * 2 * math.pi / len(nodes)))
        for index in range(len(nodes))
    }
    figure = go.Figure()
    for source, target in edges:
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        figure.add_trace(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None], mode="lines",
            line=dict(color="#cbd5e1", width=1), hoverinfo="skip", showlegend=False,
        ))
    colors = {"paper": "#2563eb", "evidence": "#10b981", "gap": "#f97316"}
    for kind in ("paper", "evidence", "gap"):
        selected = [index for index, node in enumerate(nodes) if node[1] == kind]
        if selected:
            figure.add_trace(go.Scatter(
                x=[positions[i][0] for i in selected],
                y=[positions[i][1] for i in selected],
                mode="markers+text",
                text=[nodes[i][2] for i in selected],
                textposition="top center",
                marker=dict(size=18 if kind != "paper" else 24, color=colors[kind]),
                name=kind.title(),
                customdata=[nodes[i][0] for i in selected],
                hovertemplate="<b>%{text}</b><br>%{customdata}<extra></extra>",
            ))
    figure.update_layout(
        title="Evidence provenance graph",
        height=600,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=10, r=10, t=55, b=10),
        legend=dict(orientation="h"),
        plot_bgcolor="white",
    )
    st.plotly_chart(figure, width="stretch", key="evidence-provenance-graph")


def _show_results(result: dict[str, Any]) -> None:
    """Render the research report and download actions."""
    papers = result.get("papers", [])
    summaries = {item.source_id: item for item in result.get("summaries", [])}
    gaps = result.get("gaps", [])
    verifications = result.get("verifications", [])
    if "shortlist" not in st.session_state:
        st.session_state["shortlist"] = set()
    if "research_history" not in st.session_state:
        st.session_state["research_history"] = []

    if result.get("error"):
        st.error(f"The run stopped safely: {result['error']}")
    if result.get("paper_errors"):
        with st.expander(f"{len(result['paper_errors'])} paper(s) could not be fully downloaded"):
            st.warning(
                "Those papers remain in the results, but their source text was not available. "
                "Other papers were processed normally."
            )
            for error in result["paper_errors"]:
                st.write(f"• {error}")
    intent = result.get("intent")
    if intent:
        with st.expander("How HorizonForge understood your request"):
            st.write(f"**Interpreted topic:** {intent['topic']}")
            st.write(f"**Task:** {intent['intent']} · **Confidence:** {intent['confidence']:.0%}")
            if intent["subtopics"]:
                st.write("**Subtopics:** " + ", ".join(intent["subtopics"]))
            if intent["constraints"]:
                st.write("**Constraints:** " + ", ".join(intent["constraints"]))
            if intent["year_from"] or intent["year_to"]:
                st.write(f"**Years:** {intent['year_from'] or 'any'}–{intent['year_to'] or 'any'}")
    if not papers:
        st.info("No papers were found. Try a broader topic or check your API/network settings.")
        return

    st.success(f"Found {len(papers)} paper(s). Every result below keeps its source ID.")
    st.caption("Sources include Semantic Scholar, arXiv, OpenAlex, Crossref, and optional IEEE Xplore.")
    _show_result_metrics(papers, summaries, verifications)
    st.divider()
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        sort_by = st.selectbox("Sort papers by", ["Quality", "Newest", "Citations"])
    with filter_col2:
        providers = sorted({paper.provider for paper in papers})
        provider_filter = st.multiselect("Providers", providers, default=providers)
    with filter_col3:
        min_quality = st.slider("Minimum quality score", 0, 100, 0)
    show_details = st.checkbox("Show full paper cards", value=False, help="Turn this on for abstracts and structured summaries.")
    filtered = [
        paper for paper in papers
        if paper.provider in provider_filter
        and paper.quality_score >= min_quality
        and (paper.year is None or paper.year >= st.session_state.get("year_from", 1900))
        and (paper.year is None or paper.year <= st.session_state.get("year_to", 2100))
        and (not st.session_state.get("prefer_open_access", True) or bool(paper.url))
        and (st.session_state.get("include_preprints", True) or paper.provider != "arxiv")
    ]
    profile = st.session_state.get("search_profile", "Balanced evidence")
    if profile == "Recent research" or sort_by == "Newest":
        filtered.sort(key=lambda paper: paper.year or 0, reverse=True)
    elif profile == "High-citation discovery" or sort_by == "Citations":
        filtered.sort(key=lambda paper: paper.citation_count or 0, reverse=True)
    else:
        filtered.sort(key=lambda paper: paper.ranking_score(), reverse=True)
    tab_papers, tab_explain, tab_compare, tab_gaps, tab_verify, tab_queue, tab_insights, tab_proposal, tab_export = st.tabs(
        ["📚 Papers & summaries", "🧩 Explain a paper", "🆚 Compare papers", "💡 Research gaps", "✅ Verification", "📌 Reading queue", "📈 Insights", "🧪 Proposal Lab", "⬇️ Export"]
    )
    with tab_papers:
        st.caption(f"Showing {len(filtered)} of {len(papers)} papers")
        overview_rows = [
            {
                "Title": paper.title[:75],
                "Source": paper.source_id,
                "Venue": paper.venue or "not found",
                "Year": paper.year or "not found",
                "Provider": paper.provider,
                "Score": paper.quality_score,
                "Citations": paper.citation_count or "not found",
            }
            for paper in filtered
        ]
        st.dataframe(overview_rows, width="stretch", hide_index=True)
        if show_details:
            for paper in filtered:
                is_saved = paper.source_id in st.session_state["shortlist"]
                if st.button(
                    "Remove from reading queue" if is_saved else "Add to reading queue",
                    key=f"queue-{paper.source_id}",
                ):
                    if is_saved:
                        st.session_state["shortlist"].remove(paper.source_id)
                    else:
                        st.session_state["shortlist"].add(paper.source_id)
                    st.rerun()
                _show_paper_card(paper, summaries.get(paper.source_id))
        else:
            st.info("Enable **Show full paper cards** above to inspect abstracts and summaries.")
    with tab_explain:
        labels = {f"{paper.title[:80]} · {paper.source_id}": paper for paper in papers}
        selected_label = st.selectbox("Choose a paper to explain", list(labels))
        selected_paper = labels[selected_label]
        selected_summary = summaries.get(selected_paper.source_id)
        explainer = PaperExplainer(_build_orchestrator(20).reader.llm)
        if st.button("Create visual explanation", key="explain-paper"):
            explanation = explainer.explain(selected_paper, selected_summary)
            st.session_state["explanation"] = explanation
        explanation = st.session_state.get("explanation")
        if explanation and explanation.source_id == selected_paper.source_id:
            st.markdown(f"### {explanation.title}")
            st.write(explanation.overview)
            _show_visual_explanation(explanation)
            st.write("**Key terms:** " + (", ".join(explanation.key_terms) or "not found"))
        st.divider()
        st.markdown("### Ask the paper tutor")
        question = st.text_input(
            "Ask a question about this paper",
            placeholder="What problem does this paper solve, and what are its limitations?",
            key=f"paper-question-{selected_paper.source_id}",
        )
        if st.button("Ask tutor", key="ask-paper") and question.strip():
            with st.spinner("Evidence analyst, teacher, and verifier are checking the source..."):
                answer = explainer.answer(selected_paper, selected_summary, question.strip())
            st.markdown(answer)
    with tab_compare:
        compare_options = {
            f"{paper.title[:70]} · {paper.source_id}": paper for paper in papers
        }
        selected_labels = st.multiselect(
            "Choose 2–4 papers to compare",
            list(compare_options),
            max_selections=4,
        )
        if len(selected_labels) < 2:
            st.info("Select at least two papers to compare their evidence side by side.")
        else:
            rows = []
            for label in selected_labels:
                paper = compare_options[label]
                summary = summaries.get(paper.source_id)
                rows.append({
                    "Paper": paper.title[:55],
                    "Source ID": paper.source_id,
                    "Provider": paper.provider,
                    "Year": paper.year or "not found",
                    "Quality": paper.quality_score,
                    "Problem": summary.problem if summary else "not found",
                    "Method": summary.method if summary else "not found",
                    "Results": summary.results if summary else "not found",
                })
            st.dataframe(rows, width="stretch", hide_index=True)
    with tab_gaps:
        if len(filtered) < len(papers):
            st.info("Gap analysis uses all retrieved papers, not only the display filter.")
        if gaps:
            for gap in gaps:
                st.markdown(f"**{gap.claim}**")
                st.caption("Supported by: " + ", ".join(gap.source_ids))
                st.divider()
        else:
            st.info("No source-backed gaps were produced.")
    with tab_verify:
        verified = sum(item.exists for item in verifications)
        st.metric("Verified paper identities", f"{verified}/{len(verifications)}")
        for item in verifications:
            icon = "✅" if item.exists and item.supported else "⚠️"
            st.write(f"{icon} **{item.source_id}** — " + (", ".join(item.flags) or "identity verified"))
    with tab_queue:
        queued = [paper for paper in papers if paper.source_id in st.session_state["shortlist"]]
        st.subheader("Your reading queue")
        if not queued:
            st.info("Add papers from the full paper cards to build a focused reading queue.")
        else:
            st.success(f"{len(queued)} paper(s) saved for follow-up.")
            for paper in queued:
                st.write(f"**{paper.title}** · `{paper.source_id}` · score {paper.quality_score}/100")
            st.download_button(
                "Download queue CSV",
                _paper_csv(queued),
                file_name="horizonforge-reading-queue.csv",
                mime="text/csv",
            )
    with tab_insights:
        import plotly.express as px
        import pandas as pd

        st.subheader("Research intelligence")
        timeline = [
            {
                "year": paper.year,
                "ranking": paper.ranking_score(),
                "provider": paper.provider,
                "title": paper.title,
            }
            for paper in papers
            if paper.year is not None
        ]
        if timeline:
            chart = px.scatter(
                pd.DataFrame(timeline),
                x="year",
                y="ranking",
                color="provider",
                hover_name="title",
                title="Publication timeline and explainable ranking",
                labels={"year": "Publication year", "ranking": "Ranking score"},
            )
            chart.update_layout(height=430, margin=dict(l=10, r=10, t=55, b=10))
            st.plotly_chart(chart, width="stretch", key="research-timeline")
        else:
            st.info("Publication years were not available for a timeline.")

        st.subheader("Evidence explorer")
        evidence_labels = {f"{paper.title[:70]} · {paper.source_id}": paper for paper in papers}
        evidence_label = st.selectbox("Choose a paper", list(evidence_labels), key="evidence-paper")
        evidence_paper = evidence_labels[evidence_label]
        evidence_summary = summaries.get(evidence_paper.source_id)
        if evidence_summary:
            field = st.selectbox(
                "Inspect evidence section",
                ["problem", "method", "data", "results", "limitations"],
                key="evidence-field",
            )
            st.info(getattr(evidence_summary, field))
            st.caption(f"Source ID: {evidence_summary.source_id}")
            with st.expander("Show extracted source context"):
                st.code(evidence_summary.source_text[:6000] or "not found")
        else:
            st.warning("This paper has no structured summary yet. Use Explain a paper to analyze it.")
        st.subheader("Evidence provenance")
        _show_evidence_graph(papers, summaries, gaps)
    with tab_proposal:
        st.subheader("Proposal Lab")
        st.caption(
            "Draft a source-linked research concept from the retrieved evidence. "
            "This is a starting point for supervision, not a claim of novelty."
        )
        if st.button("Draft source-linked proposal", key="draft-proposal"):
            proposal_llm = _build_orchestrator(20).reader.llm
            proposal = ProposalLab(proposal_llm).draft(
                result.get("topic", "not found"),
                list(summaries.values()),
                gaps,
            )
            st.session_state["proposal"] = proposal
        proposal = st.session_state.get("proposal")
        if proposal:
            st.markdown(f"### {proposal.title}")
            proposal_columns = st.columns(2)
            fields = [
                ("Motivation", proposal.motivation),
                ("Research question", proposal.research_question),
                ("Hypothesis", proposal.hypothesis),
                ("Proposed method", proposal.proposed_method),
                ("Evaluation plan", proposal.evaluation_plan),
                ("Risks", proposal.risks),
            ]
            for index, (label, value) in enumerate(fields):
                proposal_columns[index % 2].markdown(f"**{label}**  \n{value}")
            st.caption("Supporting source IDs: " + (", ".join(proposal.source_ids) or "not found"))
            st.download_button(
                "Download proposal draft",
                json.dumps(proposal.to_dict(), indent=2),
                file_name="horizonforge-proposal.json",
                mime="application/json",
            )
    with tab_export:
        report = {
            "topic": result.get("topic", "not found"),
            "intent": result.get("intent", {}),
            "papers": _records(papers),
            "summaries": _records(result.get("summaries", [])),
            "gaps": _records(gaps),
            "verifications": _records(verifications),
        }
        st.download_button(
            "Download report (JSON)",
            json.dumps(report, indent=2, ensure_ascii=False),
            file_name="horizonforge-report.json",
            mime="application/json",
        )
        st.download_button(
            "Download paper table (CSV)",
            _paper_csv(papers),
            file_name="horizonforge-papers.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download citations (BibTeX)",
            "\n".join(_bibtex(paper) for paper in papers),
            file_name="horizonforge-citations.bib",
            mime="application/x-bibtex",
        )
        st.caption("The export includes metadata and summaries, but not full extracted PDF text.")
    with st.expander("Session research history"):
        history = st.session_state.get("research_history", [])
        if history:
            st.dataframe(history, width="stretch", hide_index=True)
        else:
            st.caption("Completed searches will appear here during this session.")


st.markdown(
    '<div class="hero"><h1>🔭 HorizonForge Research Desk</h1>'
    "<p>Search papers, understand the evidence, discover gaps, and verify citations.</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Research workspace")
    st.caption("Start simple, then open Advanced controls when you need them.")
    limit = st.slider("Papers to review", 20, 50, 20)
    with st.expander("Advanced controls"):
        st.session_state["search_profile"] = st.selectbox(
            "Search profile",
            ["Balanced evidence", "Recent research", "High-citation discovery"],
        )
        st.session_state["prefer_open_access"] = st.checkbox("Prefer open-access sources", value=True)
        st.session_state["include_preprints"] = st.checkbox("Include preprints", value=True)
        st.session_state["year_from"], st.session_state["year_to"] = st.slider(
            "Publication year range", 1900, 2100, (2018, 2100)
        )
        st.session_state["enabled_sources"] = st.multiselect(
            "Enabled sources",
            ["Semantic Scholar", "arXiv", "OpenAlex", "Crossref", "IEEE Xplore"],
            default=["Semantic Scholar", "arXiv", "OpenAlex", "Crossref", "IEEE Xplore"],
        )
        st.caption("Source selection is applied to the next research run.")
    with st.expander("Scholarly provider directory"):
        _show_provider_directory()
    with st.expander("How the system works"):
        _show_methodology()
        st.caption("Provider and venue filters are available after a run.")
    st.divider()
    st.markdown("**Workflow**")
    st.markdown("1. Search scholarly indexes\n2. Read open-access sources\n3. Find source-backed gaps\n4. Verify paper identities")
    st.caption("Crossref is public. IEEE Xplore appears when `IEEE_API_KEY` is configured.")
    if st.button("Clear current report"):
        st.session_state.pop("result", None)
        st.rerun()

st.markdown('<div class="eyebrow">Research question</div>', unsafe_allow_html=True)
topic = st.text_area(
    "What would you like to research?",
    value=st.session_state.get("topic", ""),
    height=90,
    placeholder="Example: How do retrieval-augmented generation systems reduce factual errors?",
    help="Use a focused question or topic for better paper ranking.",
)
st.session_state["topic"] = topic

examples = ["RAG for scientific literature", "small language models for edge devices", "AI safety evaluation"]
st.markdown("**Quick starts**")
example_columns = st.columns(3)
for column, example in zip(example_columns, examples):
    if column.button(example, key=f"example-{example}", width="stretch"):
        st.session_state["topic"] = example
        st.rerun()

if st.button("🚀 Start research", type="primary", width="stretch", disabled=not topic.strip()):
    with st.status("Running HorizonForge agents...", expanded=True) as status:
        st.write("Searching Semantic Scholar, arXiv, and OpenAlex...")
        try:
            intent, orchestrator = _understand_request(topic.strip(), limit)
            result = orchestrator.run(intent.topic)
            result["intent"] = intent.to_dict()
            result["limit"] = intent.requested_limit or limit
            st.session_state.setdefault("research_history", []).append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "topic": intent.topic,
                "intent": intent.intent,
                "papers": len(result.get("papers", [])),
            })
            st.session_state["result"] = result
            status.update(label="Research complete", state="complete", expanded=False)
        except Exception as exc:
            st.session_state["result"] = {"topic": topic.strip(), "error": str(exc)}
            status.update(label="Research stopped safely", state="error", expanded=True)

if "result" in st.session_state:
    _show_results(st.session_state["result"])
else:
    st.info("Enter a topic above and select **Start research** to create your first report.")

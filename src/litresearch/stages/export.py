"""Stage 6: export reports and artifacts."""

from pathlib import Path

from rich.console import Console

from litresearch.config import Settings
from litresearch.exporters.zotero import export_to_zotero
from litresearch.llm import LLMError, call_llm
from litresearch.models import AnalysisResult, Paper, PipelineState, RunMetrics
from litresearch.prompts import load_prompt

console = Console()


def _format_ris_entry(paper: Paper) -> str:
    lines = ["TY  - JOUR"]
    lines.append(f"TI  - {paper.title}")
    for author in paper.authors:
        lines.append(f"AU  - {author}")
    if paper.year is not None:
        lines.append(f"PY  - {paper.year}")
    if paper.venue:
        lines.append(f"JO  - {paper.venue}")
    if paper.doi:
        lines.append(f"DO  - {paper.doi}")
    lines.append("ER  -")
    return "\n".join(lines)


def _build_synthesis(
    questions: list[str],
    top_analyses: list[AnalysisResult],
    settings: Settings,
) -> str:
    prompt = load_prompt("synthesis")
    user_content = "\n".join(
        [
            "Research questions:",
            *[f"- {question}" for question in questions],
            "",
            "Top paper analyses:",
            *[
                "\n".join(
                    [
                        f"Paper ID: {analysis.paper_id}",
                        f"Summary: {analysis.summary}",
                        f"Key findings: {', '.join(analysis.key_findings)}",
                        f"Methodology: {analysis.methodology}",
                        f"Relevance rationale: {analysis.relevance_rationale}",
                    ]
                )
                for analysis in top_analyses
            ],
        ]
    )

    try:
        return call_llm(settings, prompt, user_content, expect_json=False)
    except LLMError as exc:
        console.print(f"[yellow]Synthesis failed:[/yellow] {exc}")
        return "## Synthesis\n\nSynthesis generation failed for this run."


def run(
    state: PipelineState,
    settings: Settings,
    run_metrics: RunMetrics | None = None,
) -> PipelineState:
    """Write reports, reference files, and JSON data."""
    output_dir = Path(state.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    papers_by_id = {paper.paper_id: paper for paper in state.candidates}
    analyses_by_id = {analysis.paper_id: analysis for analysis in state.analyses}
    top_papers = [
        papers_by_id[paper_id] for paper_id in state.ranked_paper_ids if paper_id in papers_by_id
    ]
    top_analyses = [
        analyses_by_id[paper_id]
        for paper_id in state.ranked_paper_ids
        if paper_id in analyses_by_id
    ]

    synthesis = _build_synthesis(state.questions, top_analyses, settings)

    report_lines = [
        "# Literature Research Report",
        "",
        "## Research Questions",
        *[f"- {question}" for question in state.questions],
        "",
        "## Search Strategy",
        f"- Facets: {len(state.facets)}",
        f"- Queries: {len(state.search_queries)}",
        f"- Candidate papers: {len(state.candidates)}",
        f"- Analyzed papers: {len(state.analyses)}",
        "",
        "## Top Papers",
    ]
    for paper in top_papers:
        analysis = analyses_by_id.get(paper.paper_id)
        if analysis is None:
            continue
        report_lines.extend(
            [
                f"### {paper.title}",
                f"- Authors: {', '.join(paper.authors) or 'Unknown'}",
                f"- Year: {paper.year or 'Unknown'}",
                f"- Venue: {paper.venue or 'Unknown'}",
                f"- Relevance score: {analysis.relevance_score}",
                "",
                analysis.summary,
                "",
            ]
        )
    report_lines.extend(["", "## Foundational Papers", ""])
    if state.foundational_paper_ids:
        for paper_id in state.foundational_paper_ids:
            paper = papers_by_id.get(paper_id)
            if paper is None:
                continue
            report_lines.extend(
                [
                    f"### {paper.title}",
                    f"- Authors: {', '.join(paper.authors) or 'Unknown'}",
                    f"- Year: {paper.year or 'Unknown'}",
                    f"- Venue: {paper.venue or 'Unknown'}",
                    "",
                ]
            )
    else:
        report_lines.append("No foundational papers identified.")
    report_lines.extend(["## Synthesis", "", synthesis])

    (output_dir / "report.md").write_text("\n".join(report_lines).strip() + "\n", encoding="utf-8")

    analyses_lines = ["# Paper Analyses", ""]
    for analysis in state.analyses:
        paper = papers_by_id.get(analysis.paper_id)
        title = paper.title if paper is not None else analysis.paper_id
        analyses_lines.extend(
            [
                f"## {title}",
                f"- Paper ID: {analysis.paper_id}",
                f"- Relevance score: {analysis.relevance_score}",
                f"- Relevance rationale: {analysis.relevance_rationale}",
                f"- Methodology: {analysis.methodology}",
                "",
                "### Summary",
                analysis.summary,
                "",
                "### Key Findings",
                *[f"- {finding}" for finding in analysis.key_findings],
                "",
            ]
        )
    (output_dir / "paper_analyses.md").write_text(
        "\n".join(analyses_lines).strip() + "\n",
        encoding="utf-8",
    )

    bibtex_content = "\n\n".join(paper.bibtex for paper in top_papers if paper.bibtex)
    (output_dir / "references.bib").write_text(
        bibtex_content + ("\n" if bibtex_content else ""), encoding="utf-8"
    )

    ris_content = "\n\n".join(_format_ris_entry(paper) for paper in top_papers)
    (output_dir / "references.ris").write_text(
        ris_content + ("\n" if ris_content else ""), encoding="utf-8"
    )

    updated_state = state.model_copy(
        update={
            "candidates": list(state.candidates),
            "current_stage": "export",
        }
    )
    (output_dir / "data.json").write_text(
        updated_state.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    if run_metrics is not None:
        (output_dir / "metrics.json").write_text(
            run_metrics.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )

    zotero_result: dict[str, int | list[str]] | None = None
    if settings.zotero_export:
        if not settings.zotero_library_id or not settings.zotero_api_key:
            console.print(
                "[yellow]Zotero export enabled but credentials missing:[/yellow] "
                "set zotero_library_id and zotero_api_key"
            )
        else:
            zotero_result = export_to_zotero(
                papers=top_papers,
                library_id=settings.zotero_library_id,
                api_key=settings.zotero_api_key,
                library_type=settings.zotero_library_type,
                collection_key=settings.zotero_collection_key,
                tag=settings.zotero_tag,
            )

    console.print(
        "[green]Export complete:[/green] "
        f"{len(state.candidates)} found, {len(state.analyses)} analyzed, {len(top_papers)} exported"
    )
    if zotero_result is not None:
        failed_items = zotero_result.get("failed", [])
        failed_count = 0
        if isinstance(failed_items, list):
            failed_count = len(failed_items)
        console.print(
            "[green]Zotero export:[/green] "
            f"{zotero_result.get('successful', 0)} successful, "
            f"{failed_count} failed"
        )
    return updated_state

"""Stage 6: export reports and artifacts."""

from pathlib import Path

from rich.console import Console
from rich.progress import track

from litresearch.config import Settings
from litresearch.exporters.zotero import export_to_zotero
from litresearch.llm import LLMError, call_llm
from litresearch.models import AnalysisResult, Paper, PipelineState, RunMetrics
from litresearch.pdf import download_pdf
from litresearch.prompts import load_prompt
from litresearch.utils import safe_filename

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
    if paper.open_access_pdf_url:
        lines.append(f"UR  - {paper.open_access_pdf_url}")
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
    """Write reports, reference files, JSON data, and PDFs."""
    output_dir = Path(state.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    papers_dir = output_dir / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)

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

    # Identify papers needing manual PDF sourcing
    papers_needing_pdfs = [
        paper
        for paper in top_papers
        if paper.pdf_status in ("unavailable", "not_attempted") and paper.paper_id in analyses_by_id
    ]

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
    report_lines.extend(["## Synthesis", "", synthesis])

    # Add section for papers needing manual PDFs
    if papers_needing_pdfs:
        report_lines.extend(
            [
                "",
                "## Papers Requiring Manual PDF Sourcing",
                "",
                "The following high-relevance papers were analyzed using abstracts only. ",
                "To improve analysis quality, you can manually source these PDFs and re-run:",
                "",
            ]
        )
        for paper in papers_needing_pdfs:
            analysis = analyses_by_id.get(paper.paper_id)
            report_lines.extend(
                [
                    f"### {paper.title}",
                    f"- **Paper ID**: `{paper.paper_id}`",
                    f"- **Authors**: {', '.join(paper.authors) or 'Unknown'}",
                    f"- **Year**: {paper.year or 'Unknown'}",
                    f"- **Venue**: {paper.venue or 'Unknown'}",
                    f"- **DOI**: {paper.doi or 'N/A'}",
                    f"- **Relevance Score**: {analysis.relevance_score if analysis else 'N/A'}",
                    "",
                ]
            )
        report_lines.extend(
            [
                "### How to Add These PDFs",
                "",
                "1. Source the PDFs via your institutional access, contacting authors,",
                "   or other means",
                "2. Save them to a directory with filenames matching the Paper ID",
                "   (e.g., `abc123.pdf`)",
                "3. Re-run with: `litresearch run 'your question' --inject-pdfs <path>`",
                "",
            ]
        )

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

    updated_candidates = list(state.candidates)
    for paper in track(top_papers, description="Downloading PDFs"):
        if not paper.open_access_pdf_url:
            continue
        if paper.pdf_status in ("downloaded", "user_provided"):
            continue
        pdf_bytes = download_pdf(paper.open_access_pdf_url)
        if pdf_bytes is None:
            continue
        target_path = papers_dir / f"{safe_filename(paper.paper_id)}.pdf"
        target_path.write_bytes(pdf_bytes)
        updated_paper = paper.model_copy(
            update={
                "pdf_status": "downloaded",
                "pdf_path": str(target_path),
            }
        )
        papers_by_id[paper.paper_id] = updated_paper

    updated_candidates = [papers_by_id[paper.paper_id] for paper in state.candidates]
    updated_state = state.model_copy(
        update={
            "candidates": updated_candidates,
            "current_stage": "export",
        }
    )
    (output_dir / "data.json").write_text(
        updated_state.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    # Write papers needing PDFs as JSON for programmatic access
    if papers_needing_pdfs:
        import json

        needing_pdfs_data = []
        for paper in papers_needing_pdfs:
            analysis = analyses_by_id.get(paper.paper_id)
            needing_pdfs_data.append(
                {
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "year": paper.year,
                    "venue": paper.venue,
                    "doi": paper.doi,
                    "relevance_score": analysis.relevance_score if analysis else None,
                }
            )
        (output_dir / "papers_needing_pdfs.json").write_text(
            json.dumps(needing_pdfs_data, indent=2) + "\n",
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

"""Stage 4: screening and extended paper analysis."""

import json
from pathlib import Path

from rich.console import Console
from rich.progress import track

from litresearch.config import Settings
from litresearch.llm import LLMError, call_llm
from litresearch.models import AnalysisResult, Paper, PipelineState, ScreeningResult
from litresearch.pdf import download_pdf, extract_text
from litresearch.prompts import load_prompt

console = Console()


def _screen_paper(
    paper: Paper,
    questions: list[str],
    settings: Settings,
    prompt: str,
) -> ScreeningResult | None:
    user_content = "\n".join(
        [
            "Research questions:",
            *[f"- {question}" for question in questions],
            "",
            f"Title: {paper.title}",
            f"Authors: {', '.join(paper.authors) or 'Unknown'}",
            f"Year: {paper.year or 'Unknown'}",
            f"Venue: {paper.venue or 'Unknown'}",
            f"Abstract: {paper.abstract or 'Unavailable'}",
        ]
    )

    try:
        response = call_llm(settings, prompt, user_content)
    except LLMError as exc:
        console.print(f"[yellow]Screening failed:[/yellow] {paper.title} ({exc})")
        return None

    try:
        payload = json.loads(response)
        return ScreeningResult(
            paper_id=paper.paper_id,
            relevance_score=payload["relevance_score"],
            rationale=payload["rationale"],
        )
    except json.JSONDecodeError:
        console.print(f"[yellow]JSON parse failed:[/yellow] {paper.title}")
        return None


def _analyze_paper(
    paper: Paper,
    questions: list[str],
    settings: Settings,
    prompt: str,
    output_dir: str,
) -> tuple[AnalysisResult | None, bool]:
    pdf_text = ""
    pdf_downloaded = False
    if paper.open_access_pdf_url:
        pdf_bytes = download_pdf(paper.open_access_pdf_url)
        if pdf_bytes is not None:
            papers_dir = Path(output_dir) / "papers"
            papers_dir.mkdir(parents=True, exist_ok=True)
            (papers_dir / f"{paper.paper_id}.pdf").write_bytes(pdf_bytes)
            pdf_downloaded = True
            pdf_text = extract_text(
                pdf_bytes,
                first_pages=settings.pdf_first_pages,
                last_pages=settings.pdf_last_pages,
            )

    extracted_text = pdf_text or "Only abstract-level information is available."
    user_content = "\n".join(
        [
            "Research questions:",
            *[f"- {question}" for question in questions],
            "",
            f"Title: {paper.title}",
            f"Authors: {', '.join(paper.authors) or 'Unknown'}",
            f"Year: {paper.year or 'Unknown'}",
            f"Venue: {paper.venue or 'Unknown'}",
            f"Abstract: {paper.abstract or 'Unavailable'}",
            "",
            "Extracted paper text:",
            extracted_text,
        ]
    )

    try:
        response = call_llm(settings, prompt, user_content)
    except LLMError as exc:
        console.print(f"[yellow]Analysis failed:[/yellow] {paper.title} ({exc})")
        return (None, pdf_downloaded)

    try:
        payload = json.loads(response)
        return (
            AnalysisResult(
                paper_id=paper.paper_id,
                summary=payload["summary"],
                key_findings=payload.get("key_findings", []),
                methodology=payload["methodology"],
                relevance_score=payload["relevance_score"],
                relevance_rationale=payload["relevance_rationale"],
            ),
            pdf_downloaded,
        )
    except json.JSONDecodeError:
        console.print(f"[yellow]JSON parse failed:[/yellow] {paper.title}")
        return (None, pdf_downloaded)


def run(state: PipelineState, settings: Settings) -> PipelineState:
    """Screen candidate papers and analyze the relevant ones."""
    screening_prompt = load_prompt("screening")
    analysis_prompt = load_prompt("analysis")
    papers_by_id = {paper.paper_id: paper for paper in state.candidates}

    screening_results: list[ScreeningResult] = []
    passed_papers: list[Paper] = []
    for paper in track(state.candidates, description="Screening papers"):
        if not paper.abstract:
            continue

        screening_result = _screen_paper(paper, state.questions, settings, screening_prompt)
        if screening_result is None:
            continue

        screening_results.append(screening_result)
        if screening_result.relevance_score >= settings.screening_threshold:
            passed_papers.append(paper)

    analyses: list[AnalysisResult] = []
    for paper in track(passed_papers, description="Analyzing papers"):
        analysis_result, pdf_downloaded = _analyze_paper(
            paper,
            state.questions,
            settings,
            analysis_prompt,
            state.output_dir,
        )
        if pdf_downloaded:
            papers_by_id[paper.paper_id] = paper.model_copy(update={"pdf_downloaded": True})
        if analysis_result is not None:
            analyses.append(analysis_result)

    updated_candidates = [papers_by_id[paper.paper_id] for paper in state.candidates]

    return state.model_copy(
        update={
            "candidates": updated_candidates,
            "screening_results": screening_results,
            "analyses": analyses,
            "current_stage": "analysis",
        }
    )

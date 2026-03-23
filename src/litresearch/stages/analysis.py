"""Stage 4: screening and extended paper analysis."""

import json

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

    payload = json.loads(response)
    return ScreeningResult(
        paper_id=paper.paper_id,
        relevance_score=payload["relevance_score"],
        rationale=payload["rationale"],
    )


def _analyze_paper(
    paper: Paper,
    questions: list[str],
    settings: Settings,
    prompt: str,
) -> AnalysisResult | None:
    pdf_text = ""
    if paper.open_access_pdf_url:
        pdf_bytes = download_pdf(paper.open_access_pdf_url)
        if pdf_bytes is not None:
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
        return None

    payload = json.loads(response)
    return AnalysisResult(
        paper_id=paper.paper_id,
        summary=payload["summary"],
        key_findings=payload.get("key_findings", []),
        methodology=payload["methodology"],
        relevance_score=payload["relevance_score"],
        relevance_rationale=payload["relevance_rationale"],
    )


def run(state: PipelineState, settings: Settings) -> PipelineState:
    """Screen candidate papers and analyze the relevant ones."""
    screening_prompt = load_prompt("screening")
    analysis_prompt = load_prompt("analysis")

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
        analysis_result = _analyze_paper(paper, state.questions, settings, analysis_prompt)
        if analysis_result is not None:
            analyses.append(analysis_result)

    return state.model_copy(
        update={
            "screening_results": screening_results,
            "analyses": analyses,
            "current_stage": "analysis",
        }
    )

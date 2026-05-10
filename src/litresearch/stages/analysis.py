"""Stage 4: screening and extended paper analysis."""

import math
import re

from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import track

from litresearch.config import Settings
from litresearch.llm import LLMError, call_llm
from litresearch.models import AnalysisResult, Paper, PipelineState, ScreeningResult
from litresearch.prompts import load_prompt
from litresearch.utils import parse_llm_json

console = Console()


class _ScreeningPayload(BaseModel):
    relevance_score: int
    rationale: str


class _AnalysisPayload(BaseModel):
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    methodology: str
    relevance_score: int
    relevance_rationale: str


def _select_papers_for_analysis(
    screened_papers: list[tuple[Paper, ScreeningResult, int]],
    settings: Settings,
) -> list[Paper]:
    sorted_screened = sorted(
        screened_papers,
        key=lambda item: (
            -item[1].relevance_score,
            -item[0].citation_count,
            -(item[0].year or 0),
            item[2],
        ),
    )

    if settings.screening_selection_mode == "threshold":
        return [
            paper
            for paper, screening_result, _ in sorted_screened
            if screening_result.relevance_score >= settings.screening_threshold
        ]

    if settings.screening_selection_mode == "top_k":
        if settings.screening_top_k is None or settings.screening_top_k <= 0:
            raise ValueError("screening_top_k must be > 0 when screening_selection_mode=top_k")
        return [paper for paper, _, _ in sorted_screened[: settings.screening_top_k]]

    if settings.screening_selection_mode == "top_percent":
        if not (0 < settings.screening_top_percent <= 1):
            raise ValueError(
                "screening_top_percent must be in (0, 1] when screening_selection_mode=top_percent"
            )
        if not sorted_screened:
            return []
        selected_count = max(1, math.ceil(len(sorted_screened) * settings.screening_top_percent))
        return [paper for paper, _, _ in sorted_screened[:selected_count]]

    raise ValueError(f"Unsupported screening_selection_mode: {settings.screening_selection_mode}")


def _build_keywords(questions: list[str], title: str) -> list[str]:
    terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9-]{2,}", " ".join([*questions, title]))
    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        lowered = term.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(lowered)
    return unique


def _screen_paper(
    paper: Paper,
    questions: list[str],
    settings: Settings,
    prompt: str,
) -> ScreeningResult | None:
    if not paper.abstract:
        return None

    user_content = "\n".join(
        [
            "Research questions:",
            *[f"- {question}" for question in questions],
            "",
            f"Title: {paper.title}",
            f"Authors: {', '.join(paper.authors) or 'Unknown'}",
            f"Year: {paper.year or 'Unknown'}",
            f"Venue: {paper.venue or 'Unknown'}",
            f"Abstract: {paper.abstract}",
        ]
    )

    try:
        response = call_llm(settings, prompt, user_content)
    except LLMError as exc:
        console.print(f"[yellow]Screening failed:[/yellow] {paper.title} ({exc})")
        return None

    payload = parse_llm_json(response, _ScreeningPayload, console=console)
    if payload is None:
        console.print(f"[yellow]JSON parse failed:[/yellow] {paper.title}")
        return None

    return ScreeningResult(paper_id=paper.paper_id, **payload)


def _analyze_paper(
    paper: Paper,
    questions: list[str],
    settings: Settings,
    prompt: str,
) -> tuple[AnalysisResult | None, Paper]:
    extracted_text = paper.abstract or "Only abstract-level information is available."
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
        return (None, paper)

    payload = parse_llm_json(response, _AnalysisPayload, console=console)
    if payload is None:
        console.print(f"[yellow]JSON parse failed:[/yellow] {paper.title}")
        return (None, paper)

    return (AnalysisResult(paper_id=paper.paper_id, **payload), paper)


def run(
    state: PipelineState,
    settings: Settings,
) -> PipelineState:
    """Screen candidate papers and analyze the relevant ones."""
    screening_prompt = load_prompt("screening")
    analysis_prompt = load_prompt("analysis")

    papers_by_id = {paper.paper_id: paper for paper in state.candidates}

    if state.screened_papers_completed and state.screening_results:
        screening_results = state.screening_results
        screened_papers = [
            (
                papers_by_id[result.paper_id],
                result,
                idx,
            )
            for idx, result in enumerate(screening_results)
            if result.paper_id in papers_by_id
        ]
        console.print(
            f"[dim]Screening already completed ({len(screening_results)} papers). Skipping.[/dim]"
        )
    else:
        screening_results: list[ScreeningResult] = []
        screened_papers: list[tuple[Paper, ScreeningResult, int]] = []
        for index, paper in enumerate(track(state.candidates, description="Screening papers")):
            screening_result = _screen_paper(
                paper,
                state.questions,
                settings,
                screening_prompt,
            )
            if screening_result is None:
                continue

            screening_results.append(screening_result)
            screened_papers.append((paper, screening_result, index))

    passed_papers = _select_papers_for_analysis(screened_papers, settings)

    analyses: list[AnalysisResult] = []
    for paper in track(passed_papers, description="Analyzing papers"):
        analysis_result, updated_paper = _analyze_paper(
            paper,
            state.questions,
            settings,
            analysis_prompt,
        )
        papers_by_id[paper.paper_id] = updated_paper
        if analysis_result is not None:
            analyses.append(analysis_result)

    updated_candidates = [papers_by_id[paper.paper_id] for paper in state.candidates]

    return state.model_copy(
        update={
            "candidates": updated_candidates,
            "screening_results": screening_results,
            "screened_papers_completed": True,
            "analyses": analyses,
            "current_stage": "analysis",
        }
    )

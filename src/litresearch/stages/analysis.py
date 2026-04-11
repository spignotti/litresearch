"""Stage 4: screening and extended paper analysis."""

import math
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import track

from litresearch.config import Settings
from litresearch.llm import LLMError, call_llm
from litresearch.models import AnalysisResult, Paper, PipelineState, ScreeningResult
from litresearch.pdf import download_pdf, extract_text
from litresearch.prompts import load_prompt
from litresearch.utils import parse_llm_json, safe_filename

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


def _injected_pdf_path(paper: Paper, inject_pdfs_dir: Path | None) -> Path | None:
    if inject_pdfs_dir is None:
        return None

    inject_dir_resolved = inject_pdfs_dir.resolve()

    for candidate in [safe_filename(paper.paper_id)]:
        candidate_path = (inject_dir_resolved / f"{candidate}.pdf").resolve()
        if (
            inject_dir_resolved not in candidate_path.parents
            and candidate_path != inject_dir_resolved
        ):
            continue
        if candidate_path.exists():
            return candidate_path

    if paper.doi:
        for candidate in [safe_filename(paper.doi)]:
            candidate_path = (inject_dir_resolved / f"{candidate}.pdf").resolve()
            if (
                inject_dir_resolved not in candidate_path.parents
                and candidate_path != inject_dir_resolved
            ):
                continue
            if candidate_path.exists():
                return candidate_path

    return None


def _screening_pdf_excerpt(
    paper: Paper,
    questions: list[str],
    settings: Settings,
    inject_pdfs_dir: Path | None,
) -> str | None:
    keywords = _build_keywords(questions, paper.title)

    injected_path = _injected_pdf_path(paper, inject_pdfs_dir)
    if injected_path is not None:
        try:
            pdf_bytes = injected_path.read_bytes()
        except Exception:  # noqa: BLE001
            pdf_bytes = None
        if pdf_bytes is not None:
            return extract_text(
                pdf_bytes, token_budget=settings.pdf_token_budget, keywords=keywords
            )

    if paper.open_access_pdf_url:
        pdf_bytes = download_pdf(paper.open_access_pdf_url)
        if pdf_bytes is not None:
            return extract_text(
                pdf_bytes, token_budget=settings.pdf_token_budget, keywords=keywords
            )

    return None


def _screen_paper(
    paper: Paper,
    questions: list[str],
    settings: Settings,
    prompt: str,
    fallback_prompt: str,
    pdf_excerpt: str | None = None,
) -> ScreeningResult | None:
    if paper.abstract:
        selected_prompt = prompt
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
    else:
        if not settings.abstract_fallback:
            return None
        selected_prompt = fallback_prompt
        user_content = "\n".join(
            [
                "Research questions:",
                *[f"- {question}" for question in questions],
                "",
                "Available signals:",
                f"- Title: {paper.title}",
                f"- Authors: {', '.join(paper.authors) or 'Unknown'}",
                f"- Year: {paper.year or 'Unknown'}",
                f"- Venue: {paper.venue or 'Unknown'}",
                f"- Citation count: {paper.citation_count}",
                f"- PDF excerpt: {pdf_excerpt or 'Unavailable'}",
            ]
        )

    try:
        response = call_llm(settings, selected_prompt, user_content)
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
    output_dir: str,
    inject_pdfs_dir: Path | None,
) -> tuple[AnalysisResult | None, Paper]:
    papers_dir = Path(output_dir) / "papers"
    keywords = _build_keywords(questions, paper.title)

    pdf_text: str | None = None
    pdf_path: str | None = None
    pdf_status: Literal["downloaded", "unavailable", "user_provided"] = "unavailable"

    injected_path = _injected_pdf_path(paper, inject_pdfs_dir)
    if injected_path is not None:
        try:
            pdf_bytes = injected_path.read_bytes()
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Failed to read injected PDF:[/yellow] {injected_path} ({exc})")
            pdf_bytes = None
        if pdf_bytes is not None:
            papers_dir.mkdir(parents=True, exist_ok=True)
            target_path = papers_dir / f"{safe_filename(paper.paper_id)}.pdf"
            target_path.write_bytes(pdf_bytes)
            pdf_path = str(target_path)
            pdf_status = "user_provided"
            pdf_text = extract_text(
                pdf_bytes, token_budget=settings.pdf_token_budget, keywords=keywords
            )
    elif paper.open_access_pdf_url:
        pdf_bytes = download_pdf(paper.open_access_pdf_url)
        if pdf_bytes is not None:
            papers_dir.mkdir(parents=True, exist_ok=True)
            target_path = papers_dir / f"{safe_filename(paper.paper_id)}.pdf"
            target_path.write_bytes(pdf_bytes)
            pdf_path = str(target_path)
            pdf_status = "downloaded"
            pdf_text = extract_text(
                pdf_bytes, token_budget=settings.pdf_token_budget, keywords=keywords
            )

    data_completeness: Literal["full", "abstract_only", "metadata_only"] = "metadata_only"
    if paper.abstract and pdf_text:
        data_completeness = "full"
    elif paper.abstract:
        data_completeness = "abstract_only"

    updated_paper = paper.model_copy(
        update={
            "pdf_status": pdf_status,
            "pdf_path": pdf_path,
            "data_completeness": data_completeness,
        }
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
        return (None, updated_paper)

    payload = parse_llm_json(response, _AnalysisPayload, console=console)
    if payload is None:
        console.print(f"[yellow]JSON parse failed:[/yellow] {paper.title}")
        return (None, updated_paper)

    return (AnalysisResult(paper_id=paper.paper_id, **payload), updated_paper)


class PauseForPDFsError(Exception):
    """Raised when pipeline should pause after screening for manual PDF injection."""

    def __init__(self, papers_needing_pdfs: list[Paper], state_path: str) -> None:
        self.papers_needing_pdfs = papers_needing_pdfs
        self.state_path = state_path
        super().__init__(f"{len(papers_needing_pdfs)} papers need manual PDFs")


def run(
    state: PipelineState,
    settings: Settings,
    inject_pdfs_dir: Path | None = None,
    stop_after_screening: bool = False,
) -> PipelineState:
    """Screen candidate papers and analyze the relevant ones."""
    screening_prompt = load_prompt("screening")
    screening_fallback_prompt = load_prompt("screening_fallback")
    analysis_prompt = load_prompt("analysis")
    if inject_pdfs_dir is not None and not inject_pdfs_dir.exists():
        console.print(
            "[yellow]Inject PDFs directory not found:[/yellow] "
            f"{inject_pdfs_dir}. Continuing without injection."
        )
        inject_pdfs_dir = None

    papers_by_id = {paper.paper_id: paper for paper in state.candidates}

    screening_results: list[ScreeningResult] = []
    screened_papers: list[tuple[Paper, ScreeningResult, int]] = []
    for index, paper in enumerate(track(state.candidates, description="Screening papers")):
        pdf_excerpt = None
        if not paper.abstract:
            pdf_excerpt = _screening_pdf_excerpt(paper, state.questions, settings, inject_pdfs_dir)

        screening_result = _screen_paper(
            paper,
            state.questions,
            settings,
            screening_prompt,
            screening_fallback_prompt,
            pdf_excerpt=pdf_excerpt,
        )
        if screening_result is None:
            continue

        screening_results.append(screening_result)
        screened_papers.append((paper, screening_result, index))

    passed_papers = _select_papers_for_analysis(screened_papers, settings)

    # Check if we should stop after screening for manual PDF injection
    if stop_after_screening:
        papers_needing_pdfs = [
            paper
            for paper in passed_papers
            if paper.pdf_status in ("unavailable", "not_attempted")
            and not paper.open_access_pdf_url
            and not _injected_pdf_path(paper, inject_pdfs_dir)
        ]

        if papers_needing_pdfs:
            console.print(
                "\n[bold yellow]"
                f"{len(papers_needing_pdfs)} papers passed screening but need PDFs:[/bold yellow]"
            )
            for i, paper in enumerate(papers_needing_pdfs[:10], 1):
                console.print(f"  {i}. {paper.title}")
                console.print(f"     ID: {paper.paper_id}")
                if paper.doi:
                    console.print(f"     DOI: {paper.doi}")
                console.print()

            if len(papers_needing_pdfs) > 10:
                console.print(f"  ... and {len(papers_needing_pdfs) - 10} more\n")

            console.print("[bold]Options:[/bold]")
            console.print("  1. Source these PDFs manually, then resume with:")
            console.print(
                f"     litresearch resume {state.output_dir}/state.json --inject-pdfs <path>"
            )
            console.print("  2. Continue without PDFs (analysis will use abstracts only):")
            console.print(f"     litresearch resume {state.output_dir}/state.json\n")

            raise PauseForPDFsError(papers_needing_pdfs, state.output_dir)

    analyses: list[AnalysisResult] = []
    for paper in track(passed_papers, description="Analyzing papers"):
        analysis_result, updated_paper = _analyze_paper(
            paper,
            state.questions,
            settings,
            analysis_prompt,
            state.output_dir,
            inject_pdfs_dir,
        )
        papers_by_id[paper.paper_id] = updated_paper
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

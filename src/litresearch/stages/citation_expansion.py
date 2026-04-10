"""Citation graph expansion stage."""

from typing import Any

from rich.console import Console
from rich.progress import track
from semanticscholar import SemanticScholar

from litresearch.config import Settings
from litresearch.models import Paper, PipelineState
from litresearch.utils import retry_with_backoff

console = Console()


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "raw_data") and isinstance(value.raw_data, dict):
        return value.raw_data
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _paper_from_cited_data(cited: dict[str, Any]) -> Paper | None:
    paper_id = cited.get("paperId") or cited.get("paper_id")
    title = cited.get("title")
    if not isinstance(paper_id, str) or not isinstance(title, str) or not title:
        return None

    authors: list[str] = []
    for author in cited.get("authors") or []:
        author_data = _as_dict(author)
        name = author_data.get("name")
        if isinstance(name, str) and name:
            authors.append(name)

    external_ids = _as_dict(cited.get("externalIds") or cited.get("external_ids") or {})
    open_access_pdf = _as_dict(cited.get("openAccessPdf") or cited.get("open_access_pdf") or {})

    return Paper(
        paper_id=paper_id,
        title=title,
        abstract=cited.get("abstract"),
        authors=authors,
        year=cited.get("year"),
        citation_count=cited.get("citationCount") or cited.get("citation_count") or 0,
        venue=cited.get("venue"),
        doi=external_ids.get("DOI"),
        open_access_pdf_url=open_access_pdf.get("url"),
        source="citation_expansion",
    )


def run(state: PipelineState, settings: Settings) -> PipelineState:
    """Expand top-ranked papers by traversing their reference graph."""
    if not settings.expand_citations:
        return state.model_copy(update={"current_stage": "citation_expansion"})

    if not state.ranked_paper_ids:
        console.print("[yellow]No ranked papers to expand citations from[/yellow]")
        return state.model_copy(update={"current_stage": "citation_expansion"})

    if settings.s2_api_key:
        scholar = SemanticScholar(
            api_key=settings.s2_api_key,
            timeout=settings.s2_timeout,
            retry=False,
        )
    else:
        scholar = SemanticScholar(timeout=settings.s2_timeout, retry=False)

    top_paper_ids = state.ranked_paper_ids[: settings.top_n]
    existing_ids = {paper.paper_id for paper in state.candidates}

    reference_counts: dict[str, int] = {}
    reference_papers: dict[str, Paper] = {}

    console.print(
        f"[bold blue]Expanding citations for {len(top_paper_ids)} top papers...[/bold blue]"
    )

    for paper_id in track(top_paper_ids, description="Fetching references"):
        try:

            @retry_with_backoff(
                max_retries=settings.max_retries,
                base_delay=settings.retry_base_delay,
            )
            def fetch_references(*, current_paper_id: str = paper_id) -> Any:
                return scholar.get_paper_references(current_paper_id, limit=100)

            references = fetch_references()
            items = getattr(references, "items", references)

            for reference in items:
                ref_data = _as_dict(reference)
                cited = _as_dict(ref_data.get("citedPaper") or ref_data.get("cited_paper"))
                ref_id = cited.get("paperId") or cited.get("paper_id")
                if not isinstance(ref_id, str) or not ref_id:
                    continue

                if ref_id in existing_ids:
                    continue

                reference_counts[ref_id] = reference_counts.get(ref_id, 0) + 1

                if ref_id not in reference_papers:
                    paper = _paper_from_cited_data(cited)
                    if paper is not None:
                        reference_papers[ref_id] = paper

        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Failed to fetch references for {paper_id}:[/yellow] {exc}")
            continue

    expanded_papers = [
        paper
        for ref_id, paper in reference_papers.items()
        if reference_counts.get(ref_id, 0) >= settings.min_cross_refs
    ]
    expanded_papers.sort(key=lambda paper: paper.citation_count, reverse=True)
    expanded_papers = expanded_papers[:50]

    console.print(f"[green]Found {len(expanded_papers)} frequently referenced works[/green]")

    return state.model_copy(
        update={
            "candidates": [*state.candidates, *expanded_papers],
            "current_stage": "citation_expansion",
        }
    )

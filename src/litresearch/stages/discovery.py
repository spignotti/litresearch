"""Stage 2: paper discovery."""

from typing import Any, cast

from rich.console import Console
from rich.progress import track
from semanticscholar import SemanticScholar

from litresearch.config import Settings
from litresearch.models import Paper, PipelineState

console = Console()

SEARCH_FIELDS = [
    "title",
    "abstract",
    "authors",
    "year",
    "citationCount",
    "venue",
    "openAccessPdf",
    "externalIds",
    "citationStyles",
]


def run(state: PipelineState, settings: Settings) -> PipelineState:
    """Discover candidate papers for the generated search queries."""
    if settings.s2_api_key:
        scholar = SemanticScholar(api_key=settings.s2_api_key)
    else:
        scholar = SemanticScholar()
    papers_by_id: dict[str, Paper] = {}

    for search_query in track(state.search_queries, description="Discovering papers"):
        try:
            results = scholar.search_paper(
                search_query.query,
                fields=SEARCH_FIELDS,
                limit=settings.max_results_per_query,
            )
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Search failed:[/yellow] {search_query.query} ({exc})")
            continue

        paginated_results = cast(Any, results)
        for result in paginated_results.items:
            paper = Paper.from_s2(result)
            papers_by_id.setdefault(paper.paper_id, paper)

    return state.model_copy(
        update={
            "candidates": list(papers_by_id.values()),
            "current_stage": "discovery",
        }
    )

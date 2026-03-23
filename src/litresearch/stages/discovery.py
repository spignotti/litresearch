"""Stage 2: paper discovery."""

import time
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
        scholar = SemanticScholar(
            api_key=settings.s2_api_key,
            timeout=settings.s2_timeout,
            retry=False,
        )
    else:
        scholar = SemanticScholar(timeout=settings.s2_timeout, retry=False)

    min_interval = 0.0
    if settings.s2_requests_per_second > 0:
        min_interval = 1.0 / settings.s2_requests_per_second
    last_request_at: float | None = None

    papers_by_id: dict[str, Paper] = {}

    for search_query in track(state.search_queries, description="Discovering papers"):
        if last_request_at is not None and min_interval > 0:
            elapsed = time.monotonic() - last_request_at
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)

        try:
            results = scholar.search_paper(
                search_query.query,
                fields=SEARCH_FIELDS,
                limit=settings.max_results_per_query,
            )
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Search failed:[/yellow] {search_query.query} ({exc})")
            last_request_at = time.monotonic()
            continue

        last_request_at = time.monotonic()

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

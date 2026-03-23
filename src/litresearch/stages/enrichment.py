"""Stage 3: metadata enrichment."""

from typing import Any, cast

from rich.console import Console
from semanticscholar import SemanticScholar

from litresearch.config import Settings
from litresearch.models import Paper, PipelineState

console = Console()

ENRICHMENT_FIELDS = [
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

BATCH_SIZE = 500  # S2 /papers batch endpoint limit


def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def run(state: PipelineState, settings: Settings) -> PipelineState:
    """Fill missing metadata for discovered candidate papers."""
    if not state.candidates:
        return state.model_copy(update={"current_stage": "enrichment"})

    if settings.s2_api_key:
        scholar = SemanticScholar(
            api_key=settings.s2_api_key,
            timeout=settings.s2_timeout,
            retry=False,
        )
    else:
        scholar = SemanticScholar(timeout=settings.s2_timeout, retry=False)

    papers_by_id = {paper.paper_id: paper for paper in state.candidates}
    for batch in _chunk(list(papers_by_id), BATCH_SIZE):
        try:
            results = scholar.get_papers(batch, fields=ENRICHMENT_FIELDS)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Enrichment failed:[/yellow] {exc}")
            continue

        for result in cast(list[Any], results):
            enriched = Paper.from_s2(result)
            papers_by_id[enriched.paper_id] = papers_by_id[enriched.paper_id].model_copy(
                update=enriched.model_dump(exclude_none=True)
            )

    return state.model_copy(
        update={
            "candidates": list(papers_by_id.values()),
            "current_stage": "enrichment",
        }
    )

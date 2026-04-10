"""Stage 2: paper discovery."""

import re
import time
from typing import Any, cast

from rich.console import Console
from rich.progress import track
from semanticscholar import SemanticScholar

from litresearch.config import Settings
from litresearch.models import Paper, PipelineState
from litresearch.sources.openalex import OpenAlexClient
from litresearch.utils import retry_with_backoff

console = Console()

try:
    from rapidfuzz import fuzz  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    fuzz = None

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

TITLE_MATCH_THRESHOLD = 94.0


def _normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = value.strip().lower()
    doi = doi.removeprefix("https://doi.org/")
    doi = doi.removeprefix("http://doi.org/")
    doi = doi.removeprefix("doi:")
    return doi or None


def _normalize_title(value: str) -> str:
    lowered = value.lower().strip()
    alnum = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return " ".join(alnum.split())


def _title_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 100.0
    if fuzz is not None:
        return float(fuzz.ratio(left, right))

    from difflib import SequenceMatcher

    return SequenceMatcher(None, left, right).ratio() * 100.0


def _metadata_score(paper: Paper) -> int:
    score = 0
    if paper.abstract:
        score += 4
    if paper.open_access_pdf_url:
        score += 4
    if paper.doi:
        score += 2
    if paper.authors:
        score += 2
    if paper.year is not None:
        score += 1
    if paper.venue:
        score += 1
    if paper.bibtex:
        score += 1
    score += min(paper.citation_count // 50, 3)
    return score


def _merge_papers(existing: Paper, incoming: Paper) -> Paper:
    existing_score = _metadata_score(existing)
    incoming_score = _metadata_score(incoming)

    if incoming_score > existing_score:
        primary, secondary = incoming, existing
    else:
        primary, secondary = existing, incoming

    merged_source = primary.source
    if existing.source != incoming.source:
        merged_source = "both"

    existing_abstract = existing.abstract or ""
    incoming_abstract = incoming.abstract or ""
    merged_abstract = existing.abstract
    if len(incoming_abstract) > len(existing_abstract):
        merged_abstract = incoming.abstract

    merged_authors = (
        existing.authors if len(existing.authors) >= len(incoming.authors) else incoming.authors
    )

    return primary.model_copy(
        update={
            "title": primary.title or secondary.title,
            "abstract": merged_abstract,
            "authors": merged_authors,
            "year": primary.year if primary.year is not None else secondary.year,
            "citation_count": max(existing.citation_count, incoming.citation_count),
            "venue": primary.venue or secondary.venue,
            "doi": _normalize_doi(primary.doi) or _normalize_doi(secondary.doi),
            "open_access_pdf_url": primary.open_access_pdf_url or secondary.open_access_pdf_url,
            "bibtex": primary.bibtex or secondary.bibtex,
            "corpus_id": primary.corpus_id
            if primary.corpus_id is not None
            else secondary.corpus_id,
            "source": merged_source,
        }
    )


def _is_probable_duplicate(left: Paper, right: Paper) -> bool:
    left_doi = _normalize_doi(left.doi)
    right_doi = _normalize_doi(right.doi)
    if left_doi and right_doi and left_doi == right_doi:
        return True

    left_title = _normalize_title(left.title)
    right_title = _normalize_title(right.title)
    similarity = _title_similarity(left_title, right_title)
    if similarity < TITLE_MATCH_THRESHOLD:
        return False

    if left.year is None or right.year is None:
        return True
    return left.year == right.year


def _discover_from_s2(
    scholar: SemanticScholar,
    query: str,
    settings: Settings,
) -> list[Paper]:
    def on_retry(exc: Exception, attempt: int) -> None:
        console.print(
            f"[yellow]Search retry {attempt}/{settings.max_retries}:[/yellow] {query} ({exc})"
        )

    search_with_retry = retry_with_backoff(
        max_retries=settings.max_retries,
        base_delay=settings.retry_base_delay,
        on_retry=on_retry,
    )(scholar.search_paper)

    results = search_with_retry(
        query,
        fields=SEARCH_FIELDS,
        limit=settings.max_results_per_query,
    )

    papers: list[Paper] = []
    for result in cast(Any, results).items:
        papers.append(Paper.from_s2(result))
    return papers


def _discover_from_openalex(client: OpenAlexClient, query: str, limit: int) -> list[Paper]:
    works = client.search_papers(query=query, limit=limit)
    papers: list[Paper] = []
    for work in works:
        paper = client.work_to_paper(work)
        if paper is not None:
            papers.append(paper)
    return papers


def run(state: PipelineState, settings: Settings) -> PipelineState:
    """Discover candidate papers for the generated search queries."""
    sources = settings.discovery_sources or ["s2"]
    source_set = {source.lower() for source in sources}
    unknown_sources = sorted(source_set - {"s2", "openalex"})
    for source_name in unknown_sources:
        console.print(f"[yellow]Unknown discovery source skipped:[/yellow] {source_name}")

    scholar: SemanticScholar | None = None
    if "s2" in source_set:
        if settings.s2_api_key:
            scholar = SemanticScholar(
                api_key=settings.s2_api_key,
                timeout=settings.s2_timeout,
                retry=False,
            )
        else:
            scholar = SemanticScholar(timeout=settings.s2_timeout, retry=False)

    openalex_client: OpenAlexClient | None = None
    if "openalex" in source_set:
        openalex_client = OpenAlexClient(email=settings.openalex_email, timeout=settings.s2_timeout)

    min_interval = (
        1.0 / settings.s2_requests_per_second if settings.s2_requests_per_second > 0 else 0.0
    )
    last_s2_request_at: float | None = None

    papers_by_id: dict[str, Paper] = {}

    for search_query in track(state.search_queries, description="Discovering papers"):
        discovered: list[Paper] = []

        if scholar is not None:
            if last_s2_request_at is not None and min_interval > 0:
                elapsed = time.monotonic() - last_s2_request_at
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)

            try:
                discovered.extend(_discover_from_s2(scholar, search_query.query, settings))
            except Exception as exc:  # noqa: BLE001
                console.print(f"[yellow]S2 search failed:[/yellow] {search_query.query} ({exc})")
            last_s2_request_at = time.monotonic()

        if openalex_client is not None:
            discovered.extend(
                _discover_from_openalex(
                    openalex_client,
                    search_query.query,
                    settings.max_results_per_query,
                )
            )

        for paper in discovered:
            existing = papers_by_id.get(paper.paper_id)
            if existing is not None:
                papers_by_id[paper.paper_id] = _merge_papers(existing, paper)
                continue

            duplicate_id = None
            for candidate_id, candidate in papers_by_id.items():
                if _is_probable_duplicate(candidate, paper):
                    duplicate_id = candidate_id
                    break

            if duplicate_id is None:
                papers_by_id[paper.paper_id] = paper
                continue

            papers_by_id[duplicate_id] = _merge_papers(papers_by_id[duplicate_id], paper)

    return state.model_copy(
        update={
            "candidates": list(papers_by_id.values()),
            "current_stage": "discovery",
        }
    )

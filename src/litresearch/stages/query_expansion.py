"""Stage: iterative query expansion."""

from __future__ import annotations

from rich.console import Console

from litresearch.config import Settings
from litresearch.llm import LLMError, call_llm
from litresearch.models import PipelineState, SearchQuery
from litresearch.prompts import load_prompt
from litresearch.utils import parse_llm_json

console = Console()


def _build_expansion_input(state: PipelineState, sample_size: int) -> str:
    """Build the user prompt input from research questions and candidate abstracts."""
    parts: list[str] = []
    parts.append("Research questions:")
    for question in state.questions:
        parts.append(f"- {question}")

    # Sample top papers by citation count for the overview
    sorted_candidates = sorted(state.candidates, key=lambda p: p.citation_count, reverse=True)
    sample = sorted_candidates[:sample_size]

    parts.append(f"\nInitial candidate papers (sample of {len(sample)}, top by citations):")
    for i, paper in enumerate(sample, start=1):
        abstract = paper.abstract or "(no abstract)"
        if len(abstract) > 500:
            abstract = abstract[:500] + "..."
        parts.append(
            f"\n{i}. {paper.title} ({paper.year or 'n/a'}, {paper.venue or 'n/a'})\n   {abstract}"
        )

    return "\n".join(parts)


def run(state: PipelineState, settings: Settings) -> PipelineState:
    """Generate expansion search queries from initial candidate overview."""
    if state.query_expansion_run:
        return state

    if not state.candidates:
        console.print("[dim]No candidates available for query expansion[/dim]")
        return state.model_copy(update={"query_expansion_run": True})

    prompt = load_prompt("query_expansion")
    user_content = _build_expansion_input(state, sample_size=settings.expansion_candidate_sample)

    try:
        response = call_llm(settings, prompt, user_content)
    except LLMError as exc:
        console.print(f"[yellow]Query expansion LLM call failed, skipping:[/yellow] {exc}")
        return state.model_copy(update={"query_expansion_run": True})

    payload = parse_llm_json(response, console=console)
    if payload is None:
        console.print("[yellow]Query expansion returned invalid JSON, skipping[/yellow]")
        return state.model_copy(update={"query_expansion_run": True})

    queries_raw = payload.get("queries", [])
    if not isinstance(queries_raw, list) or len(queries_raw) == 0:
        console.print("[dim]Query expansion generated no queries[/dim]")
        return state.model_copy(update={"query_expansion_run": True})

    new_queries: list[SearchQuery] = []
    for item in queries_raw:
        if not isinstance(item, dict):
            continue
        query_text = str(item.get("query", "")).strip()
        facet_label = str(item.get("facet", "expansion")).strip()
        if query_text:
            new_queries.append(SearchQuery(query=query_text, facet=facet_label))

    max_queries = settings.max_expansion_queries
    if len(new_queries) > max_queries:
        new_queries = new_queries[:max_queries]

    console.print(f"[green]Generated {len(new_queries)} expansion queries[/green]")

    return state.model_copy(
        update={
            "search_queries": [*state.search_queries, *new_queries],
            "query_expansion_run": True,
        }
    )

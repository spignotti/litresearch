"""Stage 1: query generation."""

from rich.console import Console

from litresearch.config import Settings
from litresearch.llm import LLMError, call_llm
from litresearch.models import Facet, PipelineState, SearchQuery
from litresearch.prompts import load_prompt
from litresearch.utils import parse_llm_json

console = Console()


def run(state: PipelineState, settings: Settings) -> PipelineState:
    """Generate thematic facets and search queries from research questions."""
    prompt = load_prompt("query_gen")
    user_content = "Research questions:\n" + "\n".join(
        f"- {question}" for question in state.questions
    )
    try:
        response = call_llm(settings, prompt, user_content)
    except LLMError as exc:
        raise LLMError(f"Query generation failed: {exc}") from exc
    payload = parse_llm_json(response, console=console)
    if payload is None:
        raise LLMError("Query generation returned invalid JSON")

    facets = [Facet.model_validate(item) for item in payload.get("facets", [])]
    search_queries = [
        SearchQuery(query=query, facet=facet.name) for facet in facets for query in facet.queries
    ]

    return state.model_copy(
        update={
            "facets": facets,
            "search_queries": search_queries,
            "current_stage": "query_gen",
        }
    )

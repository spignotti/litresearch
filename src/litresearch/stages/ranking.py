"""Stage 5: rank analyzed papers."""

from litresearch.config import Settings
from litresearch.models import PipelineState


def run(state: PipelineState, settings: Settings) -> PipelineState:
    """Rank analyzed papers and keep the top-N paper IDs."""
    candidates_by_id = {paper.paper_id: paper for paper in state.candidates}
    analyses_by_id = {analysis.paper_id: analysis for analysis in state.analyses}

    def ranking_key(paper_id: str) -> tuple[int, int, int]:
        paper = candidates_by_id.get(paper_id)
        if paper is None:
            return (analyses_by_id[paper_id].relevance_score, 0, -1)
        return (
            analyses_by_id[paper_id].relevance_score,
            paper.citation_count,
            paper.year if paper.year is not None else -1,
        )

    ranked_paper_ids = sorted(analyses_by_id, key=ranking_key, reverse=True)[: settings.top_n]

    return state.model_copy(
        update={
            "ranked_paper_ids": ranked_paper_ids,
            "current_stage": "ranking",
        }
    )

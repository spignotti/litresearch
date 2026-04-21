from pathlib import Path
from types import SimpleNamespace
from typing import cast

from litresearch.config import Settings
from litresearch.models import AnalysisResult, Paper, PipelineState, S2PaperLike
from litresearch.stages import ranking


def test_pipeline_state_save_load_roundtrip(tmp_path: Path) -> None:
    state = PipelineState(
        questions=["How do LLMs affect developer productivity?"],
        current_stage="analysis",
        output_dir="output/run-1",
        created_at="2026-03-09T16:00:00Z",
        updated_at="2026-03-09T16:05:00Z",
        screened_papers_completed=True,
    )

    path = tmp_path / "state.json"
    state.save(path)

    loaded = PipelineState.load(path)

    assert loaded == state
    assert loaded.screened_papers_completed is True


def test_paper_from_s2_normalizes_fields() -> None:
    s2_paper = SimpleNamespace(
        paperId="paper-123",
        title="Example Paper",
        corpusId=456,
        abstract="Example abstract",
        authors=[SimpleNamespace(name="Ada Lovelace"), SimpleNamespace(name="Alan Turing")],
        year=2024,
        citationCount=12,
        venue="ICSE",
        externalIds={"DOI": "10.1234/example"},
        openAccessPdf={"url": "https://example.com/paper.pdf"},
        citationStyles={"bibtex": "@article{example}"},
    )

    paper = Paper.from_s2(cast(S2PaperLike, s2_paper))

    assert paper.paper_id == "paper-123"
    assert paper.authors == ["Ada Lovelace", "Alan Turing"]
    assert paper.doi == "10.1234/example"
    assert paper.open_access_pdf_url == "https://example.com/paper.pdf"
    assert paper.bibtex == "@article{example}"


def test_ranking_sorts_by_score_then_citations_then_year() -> None:
    state = PipelineState(
        questions=["q"],
        candidates=[
            Paper(paper_id="p1", title="One", citation_count=5, year=2023),
            Paper(paper_id="p2", title="Two", citation_count=10, year=2022),
            Paper(paper_id="p3", title="Three", citation_count=10, year=2024),
        ],
        analyses=[
            AnalysisResult(
                paper_id="p1",
                summary="s",
                key_findings=[],
                methodology="m",
                relevance_score=80,
                relevance_rationale="r",
            ),
            AnalysisResult(
                paper_id="p2",
                summary="s",
                key_findings=[],
                methodology="m",
                relevance_score=90,
                relevance_rationale="r",
            ),
            AnalysisResult(
                paper_id="p3",
                summary="s",
                key_findings=[],
                methodology="m",
                relevance_score=90,
                relevance_rationale="r",
            ),
        ],
        current_stage="analysis",
        output_dir="output",
        created_at="2026-03-09T16:00:00Z",
        updated_at="2026-03-09T16:00:00Z",
    )

    updated = ranking.run(state, Settings(top_n=2))

    assert updated.ranked_paper_ids == ["p3", "p2"]

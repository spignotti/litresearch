import pytest

from litresearch.config import Settings
from litresearch.models import AnalysisResult, Paper, PipelineState
from litresearch.stages.export import run


@pytest.fixture
def minimal_state(tmp_path) -> PipelineState:
    return PipelineState(
        questions=["test question"],
        candidates=[
            Paper(
                paper_id="p1",
                title="One",
                open_access_pdf_url="https://example.com/p1.pdf",
            )
        ],
        analyses=[
            AnalysisResult(
                paper_id="p1",
                summary="summary",
                key_findings=["finding"],
                methodology="experiment",
                relevance_score=80,
                relevance_rationale="fit",
            )
        ],
        ranked_paper_ids=["p1"],
        current_stage="ranking",
        output_dir=str(tmp_path),
        created_at="2026-03-09T16:00:00Z",
        updated_at="2026-03-09T16:00:00Z",
    )


def test_export_writes_report(minimal_state, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("litresearch.stages.export.load_prompt", lambda _: "")
    monkeypatch.setattr("litresearch.stages.export.call_llm", lambda *a, **kw: "synthesis")
    monkeypatch.setattr("litresearch.stages.export.download_pdf", lambda _: None)

    run(minimal_state, Settings())

    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "references.bib").exists()
    assert (tmp_path / "references.ris").exists()
    assert (tmp_path / "data.json").exists()

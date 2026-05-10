from litresearch.config import Settings
from litresearch.models import AnalysisResult, Paper, PipelineState, ScreeningResult
from litresearch.stages.analysis import run


def _make_state(tmp_path, *, papers=None, screening_results=None, screened_papers_completed=False):
    return PipelineState(
        questions=["q"],
        candidates=papers or [],
        screening_results=screening_results or [],
        screened_papers_completed=screened_papers_completed,
        current_stage="enrichment",
        output_dir=str(tmp_path),
        created_at="2026-03-09T16:00:00Z",
        updated_at="2026-03-09T16:00:00Z",
    )


def test_analysis_skips_screening_when_already_completed(tmp_path, monkeypatch) -> None:
    """When screened_papers_completed is True and screening_results exist, screening is skipped."""
    import litresearch.stages.analysis as analysis_stage

    papers = [
        Paper(paper_id="p1", title="P1", abstract="a", citation_count=10),
        Paper(paper_id="p2", title="P2", abstract="a", citation_count=5),
    ]
    existing_results = [
        ScreeningResult(paper_id="p1", relevance_score=90, rationale="fit"),
        ScreeningResult(paper_id="p2", relevance_score=80, rationale="fit"),
    ]
    state = _make_state(
        tmp_path,
        papers=papers,
        screening_results=existing_results,
        screened_papers_completed=True,
    )

    screening_call_count = 0

    def _fail_if_called(*args, **kwargs):
        nonlocal screening_call_count
        screening_call_count += 1
        raise AssertionError("Screening should not be called when already completed")

    monkeypatch.setattr(analysis_stage, "load_prompt", lambda _name: "prompt")
    monkeypatch.setattr(analysis_stage, "_screen_paper", _fail_if_called)
    monkeypatch.setattr(
        analysis_stage,
        "_analyze_paper",
        lambda paper, questions, settings, prompt: (
            AnalysisResult(
                paper_id=paper.paper_id,
                summary="summary",
                key_findings=["finding"],
                methodology="experiment",
                relevance_score=90,
                relevance_rationale="fit",
            ),
            paper,
        ),
    )

    settings = Settings(screening_selection_mode="top_k", screening_top_k=2)
    updated = run(state, settings)

    assert screening_call_count == 0
    assert len(updated.analyses) == 2
    assert updated.screened_papers_completed is True


def test_paper_without_abstract_is_skipped(tmp_path, monkeypatch) -> None:
    """Papers without abstract are skipped (return None from screening)."""
    papers = [
        Paper(paper_id="p1", title="P1", abstract=None, citation_count=10),
        Paper(paper_id="p2", title="P2", abstract="a", citation_count=5),
    ]
    state = _make_state(tmp_path, papers=papers)

    import litresearch.stages.analysis as analysis_stage

    monkeypatch.setattr(analysis_stage, "load_prompt", lambda _name: "prompt")
    monkeypatch.setattr(
        analysis_stage,
        "call_llm",
        lambda *a, **kw: '{"relevance_score": 90, "rationale": "fit"}',
    )
    monkeypatch.setattr(
        analysis_stage,
        "_analyze_paper",
        lambda paper, questions, settings, prompt: (
            AnalysisResult(
                paper_id=paper.paper_id,
                summary="summary",
                key_findings=["finding"],
                methodology="experiment",
                relevance_score=90,
                relevance_rationale="fit",
            ),
            paper,
        ),
    )

    settings = Settings(screening_selection_mode="top_k", screening_top_k=1)
    updated = run(state, settings)

    assert len(updated.screening_results) == 1
    assert updated.screening_results[0].paper_id == "p2"

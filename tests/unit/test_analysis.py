import json

from litresearch.config import Settings
from litresearch.models import AnalysisResult, Paper, PipelineState, ScreeningResult
from litresearch.stages.analysis import PauseForPDFsError, _injected_pdf_path, run


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


def test_injected_pdf_path_rejects_path_traversal(tmp_path) -> None:
    """Test that path traversal attempts are rejected in PDF injection."""
    inject_dir = tmp_path / "pdfs"
    inject_dir.mkdir()

    # Create a safe PDF file
    safe_paper = Paper(
        paper_id="safe_paper",
        title="Safe Paper",
        abstract="Abstract",
        authors=[],
        year=2024,
        citation_count=10,
        source="s2",
    )
    (inject_dir / "safe_paper.pdf").write_bytes(b"%PDF-1.0")

    # Test that safe path works
    result = _injected_pdf_path(safe_paper, inject_dir)
    assert result is not None
    assert result.name == "safe_paper.pdf"

    # Test path traversal attempt with malicious paper_id
    malicious_paper = Paper(
        paper_id="../../../etc/passwd",
        title="Malicious Paper",
        abstract="Abstract",
        authors=[],
        year=2024,
        citation_count=0,
        source="s2",
    )
    result = _injected_pdf_path(malicious_paper, inject_dir)
    assert result is None

    # Test path traversal with null bytes
    null_byte_paper = Paper(
        paper_id="safe\x00../../../etc/passwd",
        title="Null Byte Paper",
        abstract="Abstract",
        authors=[],
        year=2024,
        citation_count=0,
        source="s2",
    )
    result = _injected_pdf_path(null_byte_paper, inject_dir)
    assert result is None


def test_analysis_saves_pdf_and_marks_candidate_downloaded(tmp_path, monkeypatch) -> None:
    state = PipelineState(
        questions=["q"],
        candidates=[
            Paper(
                paper_id="p1",
                title="One",
                abstract="abstract",
                open_access_pdf_url="https://example.com/p1.pdf",
            )
        ],
        ranked_paper_ids=[],
        current_stage="enrichment",
        output_dir=str(tmp_path),
        created_at="2026-03-09T16:00:00Z",
        updated_at="2026-03-09T16:00:00Z",
    )

    import litresearch.stages.analysis as analysis_stage

    monkeypatch.setattr(analysis_stage, "load_prompt", lambda _name: "prompt")
    monkeypatch.setattr(
        analysis_stage,
        "_screen_paper",
        lambda paper, questions, settings, prompt, screening_fallback_prompt, pdf_excerpt=None: (
            ScreeningResult(
                paper_id=paper.paper_id,
                relevance_score=100,
                rationale="fit",
            )
        ),
    )
    monkeypatch.setattr(analysis_stage, "download_pdf", lambda _url: b"%PDF-1.0")
    monkeypatch.setattr(analysis_stage, "extract_text", lambda *_args, **_kwargs: "body")
    monkeypatch.setattr(
        analysis_stage,
        "call_llm",
        lambda settings, system_prompt, user_content: json.dumps(
            {
                "summary": "summary",
                "key_findings": ["finding"],
                "methodology": "experiment",
                "relevance_score": 80,
                "relevance_rationale": "fit",
            }
        ),
    )

    updated_state = run(state, Settings())

    assert updated_state.candidates[0].pdf_status == "downloaded"
    # pdf_path may be absolute or relative depending on implementation
    assert updated_state.candidates[0].pdf_path
    assert "p1.pdf" in updated_state.candidates[0].pdf_path
    assert (tmp_path / "papers" / "p1.pdf").read_bytes() == b"%PDF-1.0"
    assert len(updated_state.analyses) == 1


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
        lambda paper, questions, settings, prompt, output_dir, inject_pdfs_dir=None: (
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
    import litresearch.models as models

    monkeypatch.setattr(models, "AnalysisResult", models.AnalysisResult, raising=False)

    settings = Settings(screening_selection_mode="top_k", screening_top_k=2)
    updated = run(state, settings)

    assert screening_call_count == 0
    assert len(updated.analyses) == 2
    assert updated.screened_papers_completed is True


def test_pause_for_pdfs_carries_screening_results(tmp_path, monkeypatch) -> None:
    """PauseForPDFsError includes screening_results for checkpoint state."""
    import litresearch.stages.analysis as analysis_stage

    papers = [
        Paper(
            paper_id="p1",
            title="P1",
            abstract="a",
            citation_count=10,
            pdf_status="not_attempted",
        ),
    ]
    state = _make_state(tmp_path, papers=papers)
    settings = Settings(screening_selection_mode="top_k", screening_top_k=1)

    monkeypatch.setattr(analysis_stage, "load_prompt", lambda _name: "prompt")
    monkeypatch.setattr(
        analysis_stage,
        "_screen_paper",
        lambda paper, questions, settings, prompt, fb_prompt, pdf_excerpt=None: ScreeningResult(
            paper_id=paper.paper_id,
            relevance_score=90,
            rationale="fit",
        ),
    )

    try:
        run(state, settings, stop_after_screening=True)
    except PauseForPDFsError as exc:
        assert len(exc.screening_results) == 1
        assert exc.screening_results[0].paper_id == "p1"
    else:
        raise AssertionError("Expected PauseForPDFsError")

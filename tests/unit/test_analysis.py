import json

from litresearch.config import Settings
from litresearch.models import Paper, PipelineState, ScreeningResult
from litresearch.stages.analysis import _injected_pdf_path, run


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

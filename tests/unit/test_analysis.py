import json

from litresearch.config import Settings
from litresearch.models import Paper, PipelineState, ScreeningResult
from litresearch.stages.analysis import run


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
        lambda paper, questions, settings, prompt: ScreeningResult(
            paper_id=paper.paper_id,
            relevance_score=100,
            rationale="fit",
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

    assert updated_state.candidates[0].pdf_downloaded is True
    assert (tmp_path / "papers" / "p1.pdf").read_bytes() == b"%PDF-1.0"
    assert len(updated_state.analyses) == 1

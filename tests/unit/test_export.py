from litresearch.config import Settings
from litresearch.models import AnalysisResult, Paper, PipelineState
from litresearch.stages.export import _format_ris_entry, run


def test_format_ris_entry_includes_expected_fields() -> None:
    paper = Paper(
        paper_id="p1",
        title="Example Paper",
        authors=["Ada Lovelace", "Alan Turing"],
        year=2024,
        venue="ICSE",
        doi="10.1234/example",
        open_access_pdf_url="https://example.com/paper.pdf",
    )

    entry = _format_ris_entry(paper)

    assert "TY  - JOUR" in entry
    assert "TI  - Example Paper" in entry
    assert "AU  - Ada Lovelace" in entry
    assert "AU  - Alan Turing" in entry
    assert "PY  - 2024" in entry
    assert "JO  - ICSE" in entry
    assert "DO  - 10.1234/example" in entry
    assert "UR  - https://example.com/paper.pdf" in entry
    assert entry.endswith("ER  -")


def test_export_skips_missing_bibtex(tmp_path) -> None:
    state = PipelineState(
        questions=["q"],
        candidates=[
            Paper(paper_id="p1", title="One", bibtex="@article{p1}"),
            Paper(paper_id="p2", title="Two", bibtex=None),
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
        ranked_paper_ids=["p1", "p2"],
        current_stage="ranking",
        output_dir=str(tmp_path),
        created_at="2026-03-09T16:00:00Z",
        updated_at="2026-03-09T16:00:00Z",
    )

    import litresearch.stages.export as export_stage

    export_stage.call_llm = lambda settings, system_prompt, user_content, expect_json=False: (
        "## Consensus\n\nDone."
    )
    export_stage.download_pdf = lambda url: None

    run(state, Settings())

    bibtex = (tmp_path / "references.bib").read_text(encoding="utf-8")
    assert bibtex.strip() == "@article{p1}"

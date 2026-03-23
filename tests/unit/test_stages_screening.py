"""Tests for screening and analysis stage."""

from unittest.mock import patch

from litresearch.config import Settings
from litresearch.models import Paper, PipelineState
from litresearch.stages.analysis import run


class TestScreeningStage:
    """Test paper screening behavior."""

    def test_paper_without_abstract_gets_zero_score(self, tmp_path) -> None:
        """Test that papers without abstract get screening result with score 0."""
        settings = Settings(
            default_model="test-model",
            screening_threshold=50,
            pdf_first_pages=4,
            pdf_last_pages=2,
        )

        paper_no_abstract = Paper(
            paper_id="123",
            title="Test Paper",
            authors=["Author"],
            year=2024,
            abstract=None,
        )

        state = PipelineState(
            questions=["Test question?"],
            candidates=[paper_no_abstract],
            current_stage="enrichment",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        with patch("litresearch.stages.analysis.load_prompt", return_value="prompt"):
            with patch("litresearch.stages.analysis.call_llm"):
                result = run(state, settings)

        assert len(result.screening_results) == 1
        assert result.screening_results[0].relevance_score == 0
        assert "no abstract available" in result.screening_results[0].rationale

    def test_json_parse_failure_skips_paper(self) -> None:
        """Test that JSON parse failure returns None and skips paper."""
        from litresearch.stages.analysis import _screen_paper

        paper = Paper(
            paper_id="456",
            title="Another Paper",
            authors=["Author"],
            year=2024,
            abstract="This is an abstract",
        )

        settings = Settings(default_model="test-model")

        with patch("litresearch.stages.analysis.call_llm", return_value="invalid json"):
            result = _screen_paper(paper, ["question"], settings, "prompt")

        assert result is None

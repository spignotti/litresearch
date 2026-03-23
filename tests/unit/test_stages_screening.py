"""Tests for screening and analysis stage."""

from collections.abc import Callable
from unittest.mock import patch

import pytest

from litresearch.config import Settings
from litresearch.models import AnalysisResult, Paper, PipelineState, ScreeningResult
from litresearch.stages.analysis import run


class TestScreeningStage:
    """Test paper screening behavior."""

    @staticmethod
    def _state_with_papers(tmp_path, papers: list[Paper]) -> PipelineState:
        return PipelineState(
            questions=["Test question?"],
            candidates=papers,
            current_stage="enrichment",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

    @staticmethod
    def _analysis_stub(analyzed_ids: list[str]) -> Callable[..., tuple[AnalysisResult, bool]]:
        def _stub(
            paper: Paper,
            questions: list[str],
            settings: Settings,
            prompt: str,
            output_dir: str,
        ) -> tuple[AnalysisResult, bool]:
            analyzed_ids.append(paper.paper_id)
            return (
                AnalysisResult(
                    paper_id=paper.paper_id,
                    summary="summary",
                    key_findings=[],
                    methodology="method",
                    relevance_score=paper.citation_count,
                    relevance_rationale="rationale",
                ),
                False,
            )

        return _stub

    def test_paper_without_abstract_gets_zero_score(self, tmp_path) -> None:
        """Test that papers without abstract get screening result with score 0."""
        settings = Settings(default_model="test-model", screening_selection_mode="top_percent")

        paper_no_abstract = Paper(
            paper_id="123",
            title="Test Paper",
            authors=["Author"],
            year=2024,
            abstract=None,
        )

        state = self._state_with_papers(tmp_path, [paper_no_abstract])

        with patch("litresearch.stages.analysis.load_prompt", return_value="prompt"):
            with patch("litresearch.stages.analysis.call_llm"):
                result = run(state, settings)

        assert len(result.screening_results) == 1
        assert result.screening_results[0].relevance_score == 0
        assert "no abstract available" in result.screening_results[0].rationale

    def test_top_percent_selection_analyzes_global_top_share(self, tmp_path, monkeypatch) -> None:
        """Test global top-percent selection after screening."""
        settings = Settings(screening_selection_mode="top_percent", screening_top_percent=0.4)
        papers = [
            Paper(paper_id="p1", title="P1", abstract="a", citation_count=1),
            Paper(paper_id="p2", title="P2", abstract="a", citation_count=2),
            Paper(paper_id="p3", title="P3", abstract="a", citation_count=3),
            Paper(paper_id="p4", title="P4", abstract="a", citation_count=4),
            Paper(paper_id="p5", title="P5", abstract="a", citation_count=5),
        ]
        scores = {"p1": 90, "p2": 80, "p3": 70, "p4": 60, "p5": 50}
        analyzed_ids: list[str] = []

        monkeypatch.setattr("litresearch.stages.analysis.load_prompt", lambda _name: "prompt")
        monkeypatch.setattr(
            "litresearch.stages.analysis._screen_paper",
            lambda paper, questions, settings, prompt: ScreeningResult(
                paper_id=paper.paper_id,
                relevance_score=scores[paper.paper_id],
                rationale="fit",
            ),
        )
        monkeypatch.setattr(
            "litresearch.stages.analysis._analyze_paper",
            self._analysis_stub(analyzed_ids),
        )

        run(self._state_with_papers(tmp_path, papers), settings)

        assert analyzed_ids == ["p1", "p2"]

    def test_top_k_selection_uses_tiebreakers(self, tmp_path, monkeypatch) -> None:
        """Test top-k selection uses score, citation_count, year, then order."""
        settings = Settings(screening_selection_mode="top_k", screening_top_k=1)
        papers = [
            Paper(paper_id="p1", title="P1", abstract="a", citation_count=10, year=2020),
            Paper(paper_id="p2", title="P2", abstract="a", citation_count=20, year=2019),
            Paper(paper_id="p3", title="P3", abstract="a", citation_count=1, year=2024),
        ]
        scores = {"p1": 80, "p2": 80, "p3": 70}
        analyzed_ids: list[str] = []

        monkeypatch.setattr("litresearch.stages.analysis.load_prompt", lambda _name: "prompt")
        monkeypatch.setattr(
            "litresearch.stages.analysis._screen_paper",
            lambda paper, questions, settings, prompt: ScreeningResult(
                paper_id=paper.paper_id,
                relevance_score=scores[paper.paper_id],
                rationale="fit",
            ),
        )
        monkeypatch.setattr(
            "litresearch.stages.analysis._analyze_paper",
            self._analysis_stub(analyzed_ids),
        )

        run(self._state_with_papers(tmp_path, papers), settings)

        assert analyzed_ids == ["p2"]

    def test_threshold_selection_mode_still_supported(self, tmp_path, monkeypatch) -> None:
        """Test legacy threshold mode still controls deep analysis."""
        settings = Settings(screening_selection_mode="threshold", screening_threshold=70)
        papers = [
            Paper(paper_id="p1", title="P1", abstract="a"),
            Paper(paper_id="p2", title="P2", abstract="a"),
            Paper(paper_id="p3", title="P3", abstract="a"),
        ]
        scores = {"p1": 90, "p2": 70, "p3": 69}
        analyzed_ids: list[str] = []

        monkeypatch.setattr("litresearch.stages.analysis.load_prompt", lambda _name: "prompt")
        monkeypatch.setattr(
            "litresearch.stages.analysis._screen_paper",
            lambda paper, questions, settings, prompt: ScreeningResult(
                paper_id=paper.paper_id,
                relevance_score=scores[paper.paper_id],
                rationale="fit",
            ),
        )
        monkeypatch.setattr(
            "litresearch.stages.analysis._analyze_paper",
            self._analysis_stub(analyzed_ids),
        )

        run(self._state_with_papers(tmp_path, papers), settings)

        assert analyzed_ids == ["p1", "p2"]

    def test_invalid_top_percent_raises_value_error(self, tmp_path, monkeypatch) -> None:
        """Test invalid top-percent config fails fast with clear error."""
        settings = Settings(screening_selection_mode="top_percent", screening_top_percent=0.0)
        papers = [Paper(paper_id="p1", title="P1", abstract="a")]

        monkeypatch.setattr("litresearch.stages.analysis.load_prompt", lambda _name: "prompt")
        monkeypatch.setattr(
            "litresearch.stages.analysis._screen_paper",
            lambda paper, questions, settings, prompt: ScreeningResult(
                paper_id=paper.paper_id,
                relevance_score=90,
                rationale="fit",
            ),
        )

        with pytest.raises(ValueError, match="screening_top_percent"):
            run(self._state_with_papers(tmp_path, papers), settings)

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

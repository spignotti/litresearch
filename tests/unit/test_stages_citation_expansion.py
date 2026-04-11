"""Tests for citation_expansion stage."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from litresearch.config import Settings
from litresearch.models import Paper, PipelineState
from litresearch.stages.citation_expansion import run


class TestCitationExpansion:
    """Test citation graph expansion behavior."""

    def test_skips_when_expand_citations_disabled(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that expansion is skipped when expand_citations=False."""
        settings = Settings(expand_citations=False)
        state = PipelineState(
            questions=["Test?"],
            candidates=[],
            ranked_paper_ids=["paper1"],
            current_stage="ranking",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        result = run(state, settings)
        assert result.current_stage == "citation_expansion"
        assert len(result.candidates) == 0

    def test_skips_when_no_ranked_papers(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that expansion is skipped when no ranked papers."""
        settings = Settings(expand_citations=True)
        state = PipelineState(
            questions=["Test?"],
            candidates=[],
            ranked_paper_ids=[],
            current_stage="ranking",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        result = run(state, settings)
        assert result.current_stage == "citation_expansion"
        assert len(result.candidates) == 0

    def test_fetches_references_for_top_papers(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that references are fetched for top-N ranked papers."""
        settings = Settings(
            expand_citations=True,
            s2_api_key=None,
            s2_timeout=10,
            top_n=2,
            min_cross_refs=1,
        )
        state = PipelineState(
            questions=["Test?"],
            candidates=[
                Paper(
                    paper_id="paper1",
                    title="Paper 1",
                    abstract="Abstract",
                    authors=[],
                    year=2024,
                    citation_count=100,
                    source="s2",
                )
            ],
            ranked_paper_ids=["paper1", "paper2"],
            current_stage="ranking",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        mock_references = SimpleNamespace(
            items=[
                SimpleNamespace(
                    citedPaper=SimpleNamespace(
                        paperId="ref1",
                        title="Referenced Paper 1",
                        year=2023,
                        citationCount=50,
                        authors=[],
                    )
                ),
                SimpleNamespace(
                    citedPaper=SimpleNamespace(
                        paperId="ref2",
                        title="Referenced Paper 2",
                        year=2022,
                        citationCount=30,
                        authors=[],
                    )
                ),
            ]
        )

        mock_scholar = MagicMock()
        mock_scholar.get_paper_references.return_value = mock_references

        with patch(
            "litresearch.stages.citation_expansion.SemanticScholar",
            return_value=mock_scholar,
        ):
            result = run(state, settings)

        assert mock_scholar.get_paper_references.call_count == 2
        assert result.current_stage == "citation_expansion"

    def test_filters_by_min_cross_refs(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that papers below min_cross_refs threshold are excluded."""
        settings = Settings(
            expand_citations=True,
            s2_api_key=None,
            s2_timeout=10,
            top_n=2,
            min_cross_refs=3,
        )
        state = PipelineState(
            questions=["Test?"],
            candidates=[
                Paper(
                    paper_id="paper1",
                    title="Paper 1",
                    abstract="Abstract",
                    authors=[],
                    year=2024,
                    citation_count=100,
                    source="s2",
                )
            ],
            ranked_paper_ids=["paper1", "paper2"],
            current_stage="ranking",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        mock_references = SimpleNamespace(
            items=[
                SimpleNamespace(
                    citedPaper=SimpleNamespace(
                        paperId="ref1",
                        title="Referenced Paper 1",
                        year=2023,
                        citationCount=50,
                        authors=[],
                    )
                ),
            ]
        )

        mock_scholar = MagicMock()
        mock_scholar.get_paper_references.return_value = mock_references

        with patch(
            "litresearch.stages.citation_expansion.SemanticScholar",
            return_value=mock_scholar,
        ):
            result = run(state, settings)

        # ref1 appears only once (min_cross_refs=3), so should be filtered out
        expanded_ids = {p.paper_id for p in result.candidates if p.source == "citation_expansion"}
        assert "ref1" not in expanded_ids

    def test_respects_rate_limit(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that citation expansion throttles requests to configured RPS."""
        settings = Settings(
            expand_citations=True,
            s2_api_key=None,
            s2_timeout=10,
            s2_requests_per_second=1.0,
            top_n=2,
            min_cross_refs=1,
        )
        state = PipelineState(
            questions=["Test?"],
            candidates=[
                Paper(
                    paper_id="paper1",
                    title="Paper 1",
                    abstract="Abstract",
                    authors=[],
                    year=2024,
                    citation_count=100,
                    source="s2",
                )
            ],
            ranked_paper_ids=["paper1", "paper2"],
            current_stage="ranking",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        mock_scholar = MagicMock()
        mock_scholar.get_paper_references.return_value = SimpleNamespace(items=[])

        with (
            patch(
                "litresearch.stages.citation_expansion.SemanticScholar",
                return_value=mock_scholar,
            ),
            patch(
                "litresearch.stages.citation_expansion.time.monotonic",
                side_effect=[0.0, 0.2, 0.3, 1.3],
            ),
            patch("litresearch.stages.citation_expansion.time.sleep") as mock_sleep,
        ):
            run(state, settings)

        mock_sleep.assert_called_once()
        assert mock_sleep.call_args.args[0] == pytest.approx(0.8)

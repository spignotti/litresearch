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

    def test_foundational_detection_enabled(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that foundational papers are detected when references overlap candidates."""
        settings = Settings(
            expand_citations=True,
            s2_api_key=None,
            s2_timeout=10,
            top_n=2,
            min_cross_refs=1,
            enable_foundational_detection=True,
            foundational_papers_count=3,
        )
        existing_paper = Paper(
            paper_id="existing1",
            title="Existing Paper",
            abstract="Abstract",
            authors=["Author One"],
            year=2023,
            citation_count=80,
            source="s2",
        )
        state = PipelineState(
            questions=["Test?"],
            candidates=[existing_paper],
            ranked_paper_ids=["paper1", "paper2"],
            current_stage="ranking",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        # Both top papers reference "existing1" — that makes it foundational
        mock_references = SimpleNamespace(
            items=[
                SimpleNamespace(
                    citedPaper=SimpleNamespace(
                        paperId="existing1",
                        title="Existing Paper",
                        year=2023,
                        citationCount=80,
                        authors=[SimpleNamespace(name="Author One")],
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

        # "existing1" is cited twice (once by each top paper) — should be foundational
        assert "existing1" in result.foundational_paper_ids
        assert len(result.foundational_paper_ids) == 1

    def test_foundational_detection_disabled(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that foundational detection is skipped when disabled."""
        settings = Settings(
            expand_citations=True,
            s2_api_key=None,
            s2_timeout=10,
            top_n=2,
            min_cross_refs=1,
            enable_foundational_detection=False,
        )
        existing_paper = Paper(
            paper_id="existing1",
            title="Existing Paper",
            abstract="Abstract",
            authors=[],
            year=2023,
            citation_count=80,
            source="s2",
        )
        state = PipelineState(
            questions=["Test?"],
            candidates=[existing_paper],
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
                        paperId="existing1",
                        title="Existing Paper",
                        year=2023,
                        citationCount=80,
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

        assert result.foundational_paper_ids == []

    def test_foundational_paper_ids_sorted_by_count(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Test that foundational papers are sorted by citation count (descending)."""
        settings = Settings(
            expand_citations=True,
            s2_api_key=None,
            s2_timeout=10,
            top_n=3,
            min_cross_refs=1,
            enable_foundational_detection=True,
            foundational_papers_count=3,
        )
        existing_a = Paper(
            paper_id="existing_a",
            title="Paper A",
            abstract="A",
            authors=[],
            year=2023,
            citation_count=80,
            source="s2",
        )
        existing_b = Paper(
            paper_id="existing_b",
            title="Paper B",
            abstract="B",
            authors=[],
            year=2023,
            citation_count=70,
            source="s2",
        )
        existing_c = Paper(
            paper_id="existing_c",
            title="Paper C",
            abstract="C",
            authors=[],
            year=2023,
            citation_count=60,
            source="s2",
        )
        state = PipelineState(
            questions=["Test?"],
            candidates=[existing_a, existing_b, existing_c],
            ranked_paper_ids=["paper1", "paper2", "paper3"],
            current_stage="ranking",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        # paper1 references all three, paper2 references b and c, paper3 references only c
        calls = [
            SimpleNamespace(
                items=[
                    SimpleNamespace(
                        citedPaper=SimpleNamespace(
                            paperId="existing_a",
                            title="Paper A",
                            year=2023,
                            citationCount=80,
                            authors=[],
                        )
                    ),
                    SimpleNamespace(
                        citedPaper=SimpleNamespace(
                            paperId="existing_b",
                            title="Paper B",
                            year=2023,
                            citationCount=70,
                            authors=[],
                        )
                    ),
                    SimpleNamespace(
                        citedPaper=SimpleNamespace(
                            paperId="existing_c",
                            title="Paper C",
                            year=2023,
                            citationCount=60,
                            authors=[],
                        )
                    ),
                ]
            ),
            SimpleNamespace(
                items=[
                    SimpleNamespace(
                        citedPaper=SimpleNamespace(
                            paperId="existing_b",
                            title="Paper B",
                            year=2023,
                            citationCount=70,
                            authors=[],
                        )
                    ),
                    SimpleNamespace(
                        citedPaper=SimpleNamespace(
                            paperId="existing_c",
                            title="Paper C",
                            year=2023,
                            citationCount=60,
                            authors=[],
                        )
                    ),
                ]
            ),
            SimpleNamespace(
                items=[
                    SimpleNamespace(
                        citedPaper=SimpleNamespace(
                            paperId="existing_c",
                            title="Paper C",
                            year=2023,
                            citationCount=60,
                            authors=[],
                        )
                    ),
                ]
            ),
        ]

        mock_scholar = MagicMock()
        mock_scholar.get_paper_references.side_effect = calls

        with patch(
            "litresearch.stages.citation_expansion.SemanticScholar",
            return_value=mock_scholar,
        ):
            result = run(state, settings)

        # A cited 1 time, B cited 2 times, C cited 3 times → order: C, B, A
        assert result.foundational_paper_ids == ["existing_c", "existing_b", "existing_a"]

    def test_foundational_respects_count_setting(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Test that foundational_papers_count limits results."""
        settings = Settings(
            expand_citations=True,
            s2_api_key=None,
            s2_timeout=10,
            top_n=3,
            min_cross_refs=1,
            enable_foundational_detection=True,
            foundational_papers_count=2,
        )
        existing_a = Paper(
            paper_id="existing_a",
            title="Paper A",
            abstract="A",
            authors=[],
            year=2023,
            citation_count=80,
            source="s2",
        )
        existing_b = Paper(
            paper_id="existing_b",
            title="Paper B",
            abstract="B",
            authors=[],
            year=2023,
            citation_count=70,
            source="s2",
        )
        existing_c = Paper(
            paper_id="existing_c",
            title="Paper C",
            abstract="C",
            authors=[],
            year=2023,
            citation_count=60,
            source="s2",
        )
        state = PipelineState(
            questions=["Test?"],
            candidates=[existing_a, existing_b, existing_c],
            ranked_paper_ids=["paper1", "paper2", "paper3"],
            current_stage="ranking",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        # All three papers referenced the same way as the sort test
        calls = [
            SimpleNamespace(
                items=[
                    SimpleNamespace(
                        citedPaper=SimpleNamespace(
                            paperId="existing_a",
                            title="A",
                            year=2023,
                            citationCount=80,
                            authors=[],
                        ),
                    ),
                    SimpleNamespace(
                        citedPaper=SimpleNamespace(
                            paperId="existing_b",
                            title="B",
                            year=2023,
                            citationCount=70,
                            authors=[],
                        ),
                    ),
                    SimpleNamespace(
                        citedPaper=SimpleNamespace(
                            paperId="existing_c",
                            title="C",
                            year=2023,
                            citationCount=60,
                            authors=[],
                        ),
                    ),
                ]
            ),
            SimpleNamespace(
                items=[
                    SimpleNamespace(
                        citedPaper=SimpleNamespace(
                            paperId="existing_b",
                            title="B",
                            year=2023,
                            citationCount=70,
                            authors=[],
                        ),
                    ),
                    SimpleNamespace(
                        citedPaper=SimpleNamespace(
                            paperId="existing_c",
                            title="C",
                            year=2023,
                            citationCount=60,
                            authors=[],
                        ),
                    ),
                ]
            ),
            SimpleNamespace(
                items=[
                    SimpleNamespace(
                        citedPaper=SimpleNamespace(
                            paperId="existing_c",
                            title="C",
                            year=2023,
                            citationCount=60,
                            authors=[],
                        ),
                    ),
                ]
            ),
        ]

        mock_scholar = MagicMock()
        mock_scholar.get_paper_references.side_effect = calls

        with patch(
            "litresearch.stages.citation_expansion.SemanticScholar",
            return_value=mock_scholar,
        ):
            result = run(state, settings)

        # foundational_papers_count=2 → only top 2 by count
        assert result.foundational_paper_ids == ["existing_c", "existing_b"]

    def test_foundational_paper_ids_in_state(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test that foundational_paper_ids is stored in returned state."""
        settings = Settings(
            expand_citations=True,
            s2_api_key=None,
            s2_timeout=10,
            top_n=1,
            min_cross_refs=1,
            enable_foundational_detection=True,
        )
        existing_paper = Paper(
            paper_id="existing1",
            title="Existing Paper",
            abstract="Abstract",
            authors=[],
            year=2023,
            citation_count=80,
            source="s2",
        )
        state = PipelineState(
            questions=["Test?"],
            candidates=[existing_paper],
            ranked_paper_ids=["paper1"],
            current_stage="ranking",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        mock_references = SimpleNamespace(
            items=[
                SimpleNamespace(
                    citedPaper=SimpleNamespace(
                        paperId="existing1",
                        title="Existing Paper",
                        year=2023,
                        citationCount=80,
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

        assert result.foundational_paper_ids == ["existing1"]
        # Verify it's serializable
        json_data = result.model_dump_json()
        assert "foundational_paper_ids" in json_data

"""Tests for discovery stage."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from litresearch.config import Settings
from litresearch.models import PipelineState, SearchQuery
from litresearch.stages.discovery import run


class TestDiscoveryStage:
    """Test paper discovery behavior."""

    def test_s2_client_configured_with_timeout_and_retry(self, tmp_path) -> None:
        """Test that S2 client is created with timeout and retry=False."""
        settings = Settings(
            s2_api_key=None,
            s2_timeout=10,
            max_results_per_query=10,
        )

        query = SearchQuery(query="machine learning", facet="AI")
        state = PipelineState(
            questions=["What is ML?"],
            search_queries=[query],
            current_stage="query_gen",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        mock_scholar = MagicMock()
        mock_scholar.search_paper.return_value = SimpleNamespace(items=[])

        with patch(
            "litresearch.stages.discovery.SemanticScholar",
            return_value=mock_scholar,
        ) as mock_init:
            run(state, settings)

        mock_init.assert_called_once_with(timeout=10, retry=False)

    def test_s2_client_with_api_key(self, tmp_path) -> None:
        """Test S2 client creation with API key."""
        settings = Settings(
            s2_api_key="test-key",
            s2_timeout=15,
            max_results_per_query=10,
        )

        query = SearchQuery(query="AI", facet="Tech")
        state = PipelineState(
            questions=["What is AI?"],
            search_queries=[query],
            current_stage="query_gen",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        mock_scholar = MagicMock()
        mock_scholar.search_paper.return_value = SimpleNamespace(items=[])

        with patch(
            "litresearch.stages.discovery.SemanticScholar",
            return_value=mock_scholar,
        ) as mock_init:
            run(state, settings)

        mock_init.assert_called_once_with(api_key="test-key", timeout=15, retry=False)

    def test_paper_deduplication_by_id(self, tmp_path) -> None:
        """Test that duplicate papers are deduplicated by paper_id."""
        settings = Settings(
            s2_api_key=None,
            s2_timeout=10,
            max_results_per_query=10,
        )

        query1 = SearchQuery(query="query1", facet="Facet1")
        query2 = SearchQuery(query="query2", facet="Facet2")
        state = PipelineState(
            questions=["Question?"],
            search_queries=[query1, query2],
            current_stage="query_gen",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        mock_paper = SimpleNamespace(
            paperId="same-id",
            title="Same Paper",
            corpusId=123,
            abstract="Abstract",
            authors=[SimpleNamespace(name="Author")],
            year=2024,
            citationCount=10,
            venue="Venue",
            externalIds={"DOI": "10.1234"},
            openAccessPdf={"url": "http://example.com"},
            citationStyles={"bibtex": "@article{...}"},
        )

        mock_scholar = MagicMock()
        mock_scholar.search_paper.return_value = SimpleNamespace(items=[mock_paper])

        with patch("litresearch.stages.discovery.SemanticScholar", return_value=mock_scholar):
            result = run(state, settings)

        assert len(result.candidates) == 1
        assert result.candidates[0].paper_id == "same-id"

    def test_rate_limit_waits_between_requests(self, tmp_path) -> None:
        """Test discovery throttles requests to configured RPS."""
        settings = Settings(
            s2_api_key=None,
            s2_timeout=10,
            s2_requests_per_second=1.0,
            max_results_per_query=10,
        )

        query1 = SearchQuery(query="query1", facet="Facet1")
        query2 = SearchQuery(query="query2", facet="Facet2")
        state = PipelineState(
            questions=["Question?"],
            search_queries=[query1, query2],
            current_stage="query_gen",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        mock_scholar = MagicMock()
        mock_scholar.search_paper.return_value = SimpleNamespace(items=[])

        with (
            patch("litresearch.stages.discovery.SemanticScholar", return_value=mock_scholar),
            patch(
                "litresearch.stages.discovery.time.monotonic",
                side_effect=[0.0, 0.2, 0.3, 1.3],
            ),
            patch("litresearch.stages.discovery.time.sleep") as mock_sleep,
        ):
            run(state, settings)

        mock_sleep.assert_called_once()
        assert mock_sleep.call_args.args[0] == pytest.approx(0.8)

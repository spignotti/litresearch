"""Tests for query expansion stage."""

import json
from unittest.mock import patch

from litresearch.config import Settings
from litresearch.llm import LLMError
from litresearch.models import Paper, PipelineState
from litresearch.stages.query_expansion import run


def _dummy_state(tmp_path) -> PipelineState:
    """Build a state with candidates for testing."""
    return PipelineState(
        questions=["How do LLMs affect developer productivity?"],
        search_queries=[],
        candidates=[
            Paper(
                paper_id="p1",
                title="Paper One",
                abstract="An abstract about LLMs and coding.",
                citation_count=50,
                year=2024,
                venue="ICSE",
            ),
            Paper(
                paper_id="p2",
                title="Paper Two",
                abstract="Deep learning for software engineering.",
                citation_count=30,
                year=2023,
                venue="FSE",
            ),
        ],
        current_stage="enrichment",
        output_dir=str(tmp_path),
        created_at="2024-01-01",
        updated_at="2024-01-01",
    )


class TestQueryExpansion:
    def test_skips_when_already_run(self, tmp_path) -> None:
        """Stage returns state unchanged when query_expansion_run is True."""
        settings = Settings(default_model="test-model")
        state = _dummy_state(tmp_path).model_copy(update={"query_expansion_run": True})

        # Should not call LLM at all
        result = run(state, settings)

        assert result is state  # same object, unchanged
        assert result.query_expansion_run is True

    def test_generates_queries_from_candidates(self, tmp_path) -> None:
        """Stage generates expansion queries from candidate abstracts."""
        settings = Settings(
            default_model="test-model",
            max_expansion_queries=2,
            expansion_candidate_sample=30,
        )
        state = _dummy_state(tmp_path)

        mock_response = json.dumps(
            {
                "queries": [
                    {
                        "query": "developer experience LLM code completion",
                        "facet": "developer experience",
                    },
                    {
                        "query": "LLM debugging assistance studies",
                        "facet": "debugging",
                    },
                ]
            }
        )

        with patch(
            "litresearch.stages.query_expansion.call_llm",
            return_value=mock_response,
        ):
            result = run(state, settings)

        assert result.query_expansion_run is True
        assert len(result.search_queries) == 2
        assert result.search_queries[0].query == "developer experience LLM code completion"
        assert result.search_queries[0].facet == "developer experience"
        assert result.search_queries[1].query == "LLM debugging assistance studies"
        assert result.search_queries[1].facet == "debugging"
        # Original state unchanged
        assert len(state.search_queries) == 0

    def test_handles_llm_failure_gracefully(self, tmp_path) -> None:
        """Stage returns state with query_expansion_run=True on LLM failure."""
        settings = Settings(default_model="test-model")
        state = _dummy_state(tmp_path)

        with patch(
            "litresearch.stages.query_expansion.call_llm",
            side_effect=LLMError("API error"),
        ):
            result = run(state, settings)

        # Must return a PipelineState, not raise
        assert isinstance(result, PipelineState)
        assert result.query_expansion_run is True
        # State is otherwise unchanged (no new queries)
        assert len(result.search_queries) == len(state.search_queries)

    def test_handles_invalid_json(self, tmp_path) -> None:
        """Stage handles malformed JSON response gracefully."""
        settings = Settings(default_model="test-model")
        state = _dummy_state(tmp_path)

        with patch(
            "litresearch.stages.query_expansion.call_llm",
            return_value="not json",
        ):
            result = run(state, settings)

        assert result.query_expansion_run is True
        assert len(result.search_queries) == len(state.search_queries)

    def test_handles_empty_queries(self, tmp_path) -> None:
        """Stage handles JSON with empty queries list."""
        settings = Settings(default_model="test-model")
        state = _dummy_state(tmp_path)

        with patch(
            "litresearch.stages.query_expansion.call_llm",
            return_value=json.dumps({"queries": []}),
        ):
            result = run(state, settings)

        assert result.query_expansion_run is True
        assert len(result.search_queries) == len(state.search_queries)

    def test_skips_when_no_candidates(self, tmp_path) -> None:
        """Stage skips expansion when there are no candidates."""
        settings = Settings(default_model="test-model")
        state = PipelineState(
            questions=["Test question"],
            current_stage="enrichment",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        result = run(state, settings)

        assert result.query_expansion_run is True
        assert len(result.search_queries) == 0

    def test_respects_max_expansion_queries(self, tmp_path) -> None:
        """Stage caps the number of queries to max_expansion_queries."""
        settings = Settings(
            default_model="test-model",
            max_expansion_queries=1,
        )
        state = _dummy_state(tmp_path)

        mock_response = json.dumps(
            {
                "queries": [
                    {"query": "query one", "facet": "facet1"},
                    {"query": "query two", "facet": "facet2"},
                    {"query": "query three", "facet": "facet3"},
                ]
            }
        )

        with patch(
            "litresearch.stages.query_expansion.call_llm",
            return_value=mock_response,
        ):
            result = run(state, settings)

        assert len(result.search_queries) == 1
        assert result.search_queries[0].query == "query one"

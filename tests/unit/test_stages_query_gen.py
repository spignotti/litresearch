"""Tests for query generation stage."""

import json
from unittest.mock import patch

import pytest

from litresearch.config import Settings
from litresearch.llm import LLMError
from litresearch.models import PipelineState
from litresearch.stages.query_gen import run


class TestQueryGenStage:
    """Test query generation stage behavior."""

    def test_successful_query_generation(self, tmp_path) -> None:
        """Test successful facet and query generation."""
        settings = Settings(default_model="test-model")
        state = PipelineState(
            questions=["What is machine learning?"],
            current_stage="start",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        mock_response = json.dumps(
            {
                "facets": [
                    {
                        "name": "Supervised Learning",
                        "queries": ["supervised learning algorithms"],
                    },
                    {"name": "Deep Learning", "queries": ["neural networks", "deep learning"]},
                ]
            }
        )

        with patch("litresearch.stages.query_gen.call_llm", return_value=mock_response):
            result = run(state, settings)

        assert len(result.facets) == 2
        assert len(result.search_queries) == 3  # 1 + 2 queries
        assert result.current_stage == "query_gen"

    def test_llm_error_raises_with_message(self, tmp_path) -> None:
        """Test that LLMError is re-raised with clear message."""
        settings = Settings(default_model="test-model")
        state = PipelineState(
            questions=["What is AI?"],
            current_stage="start",
            output_dir=str(tmp_path),
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )

        with patch("litresearch.stages.query_gen.call_llm", side_effect=LLMError("API error")):
            with pytest.raises(LLMError) as exc_info:
                run(state, settings)

        assert "Query generation failed" in str(exc_info.value)

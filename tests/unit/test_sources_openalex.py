"""Tests for OpenAlex source integration."""

from types import SimpleNamespace
from unittest.mock import patch

from litresearch.sources.openalex import OpenAlexClient


class TestOpenAlexClient:
    """Test OpenAlex API client."""

    def test_client_headers_include_email(self) -> None:
        """Test that User-Agent header includes email when provided."""
        client = OpenAlexClient(email="test@example.com", timeout=30)
        assert "test@example.com" in client.headers["User-Agent"]
        assert "litresearch" in client.headers["User-Agent"]

    def test_client_headers_anonymous_without_email(self) -> None:
        """Test that User-Agent uses anonymous when no email provided."""
        client = OpenAlexClient(timeout=30)
        assert "anonymous" in client.headers["User-Agent"]

    def test_search_papers_returns_results(self) -> None:
        """Test that search_papers returns parsed results."""
        client = OpenAlexClient(timeout=30)

        mock_work = {
            "id": "https://openalex.org/W123456",
            "display_name": "Test Paper",
            "abstract_inverted_index": {
                "test": [0],
                "paper": [1],
            },
            "authorships": [{"author": {"display_name": "Author One"}}],
            "publication_year": 2024,
            "cited_by_count": 50,
            "doi": "https://doi.org/10.1234/test",
            "open_access": {"is_oa": True, "oa_url": "https://example.com/pdf"},
            "primary_location": {"source": {"display_name": "Test Journal"}},
        }

        mock_response = SimpleNamespace(
            json=lambda: {"results": [mock_work]},
            raise_for_status=lambda: None,
        )

        with patch("litresearch.sources.openalex.httpx.get", return_value=mock_response):
            results = client.search_papers("test query", limit=10)

        assert len(results) == 1
        assert results[0]["display_name"] == "Test Paper"

    def test_search_papers_handles_network_error(self) -> None:
        """Test that search_papers returns empty list on network error."""
        client = OpenAlexClient(timeout=30)

        with patch(
            "litresearch.sources.openalex.httpx.get",
            side_effect=Exception("Network error"),
        ):
            results = client.search_papers("test query", limit=10)

        assert results == []

    def test_work_to_paper_converts_correctly(self) -> None:
        """Test that work_to_paper correctly maps OpenAlex fields to Paper model."""
        work = {
            "id": "https://openalex.org/W123456",
            "display_name": "Test Paper Title",
            "abstract_inverted_index": {
                "This": [0],
                "is": [1],
                "abstract": [2],
            },
            "authorships": [
                {"author": {"display_name": "First Author"}},
                {"author": {"display_name": "Second Author"}},
            ],
            "publication_year": 2023,
            "cited_by_count": 100,
            "doi": "https://doi.org/10.1234/test",
            "open_access": {"is_oa": True, "oa_url": "https://example.com/test.pdf"},
            "primary_location": {"source": {"display_name": "Nature"}},
        }

        paper = OpenAlexClient.work_to_paper(work)

        assert paper is not None
        assert paper.paper_id == "W123456"
        assert paper.title == "Test Paper Title"
        assert paper.abstract == "This is abstract"
        assert len(paper.authors) == 2
        assert "First Author" in paper.authors
        assert paper.year == 2023
        assert paper.citation_count == 100
        assert paper.doi == "10.1234/test"
        assert paper.open_access_pdf_url == "https://example.com/test.pdf"
        assert paper.venue == "Nature"
        assert paper.source == "openalex"

    def test_work_to_paper_handles_missing_optional_fields(self) -> None:
        """Test that work_to_paper handles works with missing optional fields."""
        work = {
            "id": "https://openalex.org/W999999",
            "display_name": "Minimal Paper",
            "authorships": [],
            "publication_year": None,
            "cited_by_count": 0,
        }

        paper = OpenAlexClient.work_to_paper(work)

        assert paper is not None
        assert paper.paper_id == "W999999"
        assert paper.title == "Minimal Paper"
        assert paper.abstract is None
        assert paper.authors == []
        assert paper.year is None
        assert paper.citation_count == 0
        assert paper.doi is None

    def test_work_to_paper_handles_conference_venue(self) -> None:
        """Test that conference proceedings are detected."""
        work = {
            "id": "https://openalex.org/W111111",
            "display_name": "Conference Paper",
            "abstract_inverted_index": None,
            "authorships": [],
            "publication_year": 2024,
            "cited_by_count": 25,
            "primary_location": {"source": {"display_name": "ICML 2024 Proceedings"}},
        }

        paper = OpenAlexClient.work_to_paper(work)
        assert paper is not None
        assert "ICML 2024 Proceedings" == paper.venue

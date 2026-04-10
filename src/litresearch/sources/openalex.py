"""OpenAlex API client for paper discovery."""

from typing import Any

import httpx
from rich.console import Console

from litresearch.models import Paper
from litresearch.utils import retry_with_backoff

console = Console()


def _abstract_from_inverted_index(inverted_index: dict[str, list[int]] | None) -> str | None:
    if not inverted_index:
        return None

    index_to_token: dict[int, str] = {}
    for token, positions in inverted_index.items():
        for position in positions:
            index_to_token[position] = token

    if not index_to_token:
        return None

    tokens = [token for _, token in sorted(index_to_token.items())]
    return " ".join(tokens)


class OpenAlexClient:
    """Client for OpenAlex Works API."""

    BASE_URL = "https://api.openalex.org"

    def __init__(self, email: str | None = None, timeout: int = 30):
        self.timeout = timeout
        self.headers = {"User-Agent": f"litresearch/1.0.0 ({email or 'anonymous'})"}

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def search_papers(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search for papers matching query."""
        try:
            response = httpx.get(
                f"{self.BASE_URL}/works",
                params={
                    "search": query,
                    "per_page": min(limit, 200),
                    "filter": "has_pdf:true",
                },
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]OpenAlex search failed:[/yellow] {exc}")
            return []

    @staticmethod
    def work_to_paper(work: dict[str, Any]) -> Paper | None:
        """Convert OpenAlex work payload to Paper model."""
        try:
            authors: list[str] = []
            for authorship in work.get("authorships", []):
                author = authorship.get("author", {})
                name = author.get("display_name")
                if name:
                    authors.append(name)

            doi = work.get("doi")
            if isinstance(doi, str) and doi.startswith("https://doi.org/"):
                doi = doi[16:]

            oa_info = work.get("open_access", {}) or {}
            oa_url = oa_info.get("oa_url") if oa_info.get("is_oa") else None

            primary_location = work.get("primary_location", {}) or {}
            source = primary_location.get("source", {}) if primary_location else {}
            venue = source.get("display_name") if source else None

            abstract = _abstract_from_inverted_index(work.get("abstract_inverted_index"))

            work_id = work.get("id", "")
            if not isinstance(work_id, str):
                return None

            return Paper(
                paper_id=work_id.replace("https://openalex.org/", ""),
                title=work.get("display_name", ""),
                abstract=abstract,
                authors=authors,
                year=work.get("publication_year"),
                citation_count=work.get("cited_by_count", 0),
                venue=venue,
                doi=doi if isinstance(doi, str) else None,
                open_access_pdf_url=oa_url,
                bibtex=None,
                source="openalex",
            )
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Failed to parse OpenAlex work:[/yellow] {exc}")
            return None

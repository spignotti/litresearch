"""Zotero export integration."""

from pathlib import Path
from typing import Any

from rich.console import Console

from litresearch.models import Paper
from litresearch.utils import retry_with_backoff

console = Console()


def export_to_zotero(
    papers: list[Paper],
    library_id: str,
    api_key: str,
    library_type: str = "user",
    collection_key: str | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """Export papers to Zotero library.

    Returns a dict with ``successful`` count and ``failed`` list.
    """
    try:
        from pyzotero import zotero
    except ImportError:
        console.print("[red]pyzotero not installed. Run: uv add pyzotero[/red]")
        return {"successful": 0, "failed": ["pyzotero not installed"]}

    zot = zotero.Zotero(library_id, library_type, api_key)

    successful = 0
    failed: list[str] = []

    for paper in papers:
        try:
            item_type = "journalArticle"
            if paper.venue and any(
                token in paper.venue.lower() for token in ["conference", "proceedings", "symposium"]
            ):
                item_type = "conferencePaper"

            creators: list[dict[str, str]] = []
            for author in paper.authors:
                parts = author.split()
                if len(parts) >= 2:
                    creators.append(
                        {
                            "creatorType": "author",
                            "firstName": " ".join(parts[:-1]),
                            "lastName": parts[-1],
                        }
                    )
                else:
                    creators.append({"creatorType": "author", "name": author})

            item: dict[str, Any] = {
                "itemType": item_type,
                "title": paper.title,
                "creators": creators,
                "abstractNote": paper.abstract or "",
                "date": str(paper.year) if paper.year else "",
            }

            if paper.venue:
                if item_type == "journalArticle":
                    item["publicationTitle"] = paper.venue
                else:
                    item["conferenceName"] = paper.venue

            if paper.doi:
                item["DOI"] = paper.doi

            if paper.open_access_pdf_url:
                item["url"] = paper.open_access_pdf_url

            if collection_key:
                item["collections"] = [collection_key]

            if tag:
                item["tags"] = [{"tag": tag}]

            @retry_with_backoff(max_retries=2, base_delay=1.0)
            def create_item(payload: dict[str, Any] = item) -> dict[str, Any]:
                return zot.create_items([payload])

            result = create_item()

            if result.get("successful"):
                successful += 1

                if paper.pdf_path:
                    try:
                        pdf_full_path = Path(paper.pdf_path)
                        if pdf_full_path.exists():
                            item_key = list(result["successful"].values())[0]["key"]
                            zot.attachment_simple([str(pdf_full_path)], item_key)
                    except Exception as exc:  # noqa: BLE001
                        console.print(
                            f"[yellow]Failed to attach PDF for {paper.title}:[/yellow] {exc}"
                        )
            else:
                failed.append(f"{paper.title}: {result.get('failed', 'Unknown error')}")

        except Exception as exc:  # noqa: BLE001
            failed.append(f"{paper.title}: {exc}")
            console.print(f"[yellow]Failed to export {paper.title} to Zotero:[/yellow] {exc}")

    return {"successful": successful, "failed": failed}

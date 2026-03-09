"""PDF download and extraction helpers."""

from io import BytesIO

import httpx
from pypdf import PdfReader
from rich.console import Console

console = Console()


def extract_text(pdf_bytes: bytes, first_pages: int = 4, last_pages: int = 2) -> str:
    """Extract text from the first and last pages of a PDF."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception:  # noqa: BLE001
        return ""

    page_count = len(reader.pages)
    if page_count == 0:
        return ""

    first_page_indexes = list(range(min(first_pages, page_count)))
    last_start = max(page_count - last_pages, 0)
    last_page_indexes = list(range(last_start, page_count))
    page_indexes = sorted(set(first_page_indexes + last_page_indexes))

    parts: list[str] = []
    for page_index in page_indexes:
        try:
            page_text = reader.pages[page_index].extract_text() or ""
        except Exception:  # noqa: BLE001
            page_text = ""

        if page_text.strip():
            parts.append(f"\n--- Page {page_index + 1} ---\n{page_text.strip()}")

    return "\n".join(parts).strip()


def download_pdf(url: str) -> bytes | None:
    """Download a PDF and return its bytes on success."""
    try:
        response = httpx.get(url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]Failed to download PDF:[/yellow] {url} ({exc})")
        return None

    return response.content

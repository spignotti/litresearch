"""PDF download and extraction helpers."""

from io import BytesIO

import httpx
from pypdf import PdfReader
from rich.console import Console

console = Console()


def extract_text(
    pdf_bytes: bytes,
    token_budget: int = 4000,
    keywords: list[str] | None = None,
) -> str | None:
    """Extract text from PDF with token budget and keyword scoring.

    Args:
        pdf_bytes: Raw PDF bytes
        token_budget: Maximum tokens to extract (approx 4 chars per token)
        keywords: List of keywords to prioritize when selecting pages

    Returns:
        Extracted text or None if extraction fails
    """
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception:  # noqa: BLE001
        return None

    page_count = len(reader.pages)
    if page_count == 0:
        return None

    pages: list[tuple[int, str]] = []
    for i in range(page_count):
        try:
            text = reader.pages[i].extract_text() or ""
            if text.strip():
                pages.append((i, text.strip()))
        except Exception:  # noqa: BLE001
            continue

    if not pages:
        return None

    if keywords and len(pages) > 1:
        keyword_set = {keyword.lower() for keyword in keywords}
        scored_pages: list[tuple[int, int, str]] = []
        for idx, text in pages:
            text_lower = text.lower()
            score = sum(1 for keyword in keyword_set if keyword in text_lower)
            if idx == 0:
                score += 1
            scored_pages.append((score, idx, text))

        scored_pages.sort(key=lambda item: (-item[0], item[1]))
        pages = [(idx, text) for _, idx, text in scored_pages]

    max_chars = token_budget * 4
    parts: list[str] = []
    total_chars = 0

    for idx, text in pages:
        page_header = f"\n--- Page {idx + 1} ---\n"
        chunk = page_header + text

        if total_chars + len(chunk) > max_chars and parts:
            break

        parts.append(chunk)
        total_chars += len(chunk)

        if total_chars >= max_chars:
            break

    return "\n".join(parts).strip() if parts else None


def download_pdf(url: str) -> bytes | None:
    """Download a PDF and return its bytes on success."""
    try:
        response = httpx.get(url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]Failed to download PDF:[/yellow] {url} ({exc})")
        return None

    return response.content

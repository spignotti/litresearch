"""Shared data models for the litresearch pipeline."""

import html
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field


class S2AuthorLike(Protocol):
    """Subset of Semantic Scholar author data used by the pipeline."""

    name: str


class S2PaperLike(Protocol):
    """Subset of Semantic Scholar paper data used by the pipeline."""

    paperId: str
    title: str
    corpusId: int | None
    abstract: str | None
    authors: list[S2AuthorLike] | None
    year: int | None
    citationCount: int | None
    venue: str | None
    externalIds: dict[str, str] | None
    openAccessPdf: dict[str, str] | None
    citationStyles: dict[str, str] | None


class Facet(BaseModel):
    """A thematic facet with generated search queries."""

    name: str
    queries: list[str] = Field(default_factory=list)


class SearchQuery(BaseModel):
    """A flattened search query tied to its source facet."""

    query: str
    facet: str


class Paper(BaseModel):
    """Normalized paper metadata used throughout the pipeline."""

    paper_id: str
    corpus_id: int | None = None
    title: str
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    citation_count: int = 0
    venue: str | None = None
    doi: str | None = None
    open_access_pdf_url: str | None = None
    bibtex: str | None = None
    pdf_downloaded: bool = False

    @classmethod
    def from_s2(cls, s2_paper: S2PaperLike) -> "Paper":
        """Create a normalized paper model from a Semantic Scholar paper object."""

        external_ids = s2_paper.externalIds or {}
        open_access_pdf = s2_paper.openAccessPdf or {}
        citation_styles = s2_paper.citationStyles or {}
        authors = s2_paper.authors or []

        return cls(
            paper_id=s2_paper.paperId,
            corpus_id=s2_paper.corpusId,
            title=html.unescape(s2_paper.title),
            abstract=html.unescape(s2_paper.abstract) if s2_paper.abstract else None,
            authors=[author.name for author in authors if author.name],
            year=s2_paper.year,
            citation_count=s2_paper.citationCount or 0,
            venue=html.unescape(s2_paper.venue) if s2_paper.venue else None,
            doi=external_ids.get("DOI"),
            open_access_pdf_url=open_access_pdf.get("url"),
            bibtex=citation_styles.get("bibtex"),
        )


class ScreeningResult(BaseModel):
    """Stage 4A abstract-screening result."""

    paper_id: str
    relevance_score: int
    rationale: str


class AnalysisResult(BaseModel):
    """Stage 4B extended-analysis result."""

    paper_id: str
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    methodology: str
    relevance_score: int
    relevance_rationale: str


class PipelineState(BaseModel):
    """Serializable pipeline state for fresh runs and resume."""

    questions: list[str] = Field(default_factory=list)
    facets: list[Facet] = Field(default_factory=list)
    search_queries: list[SearchQuery] = Field(default_factory=list)
    candidates: list[Paper] = Field(default_factory=list)
    screening_results: list[ScreeningResult] = Field(default_factory=list)
    analyses: list[AnalysisResult] = Field(default_factory=list)
    ranked_paper_ids: list[str] = Field(default_factory=list)
    current_stage: str
    output_dir: str
    created_at: str
    updated_at: str

    def save(self, path: str | Path) -> None:
        """Write the pipeline state to disk as JSON."""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "PipelineState":
        """Load a pipeline state from a JSON file."""
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

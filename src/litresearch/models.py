"""Shared data models for the litresearch pipeline."""

from pydantic import BaseModel, Field


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

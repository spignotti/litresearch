# litresearch

## Identity
- **What**: CLI tool that automates literature research — from research questions to a curated, ranked, and exported set of relevant papers with structured reports.
- **Why**: Manual literature research (Elicit → PDF download → LLM summarization → manual ranking) is tedious and repetitive. This pipeline automates the entire flow end-to-end.
- **Type**: cli
- **Python**: 3.12

## Architecture
- **Framework**: Typer (CLI) + importable Python API
- **Dependencies**:
  - typer: CLI framework with type hints and auto-generated help
  - litellm: Multi-provider LLM abstraction (100+ providers via unified interface)
  - semanticscholar: Typed Python client for Semantic Scholar API (paper search, metadata, pagination)
  - pypdf: PDF text extraction (pure Python, BSD license — MIT-compatible)
  - pydantic / pydantic-settings: Config validation, typed models, TOML/ENV support
  - httpx: Async HTTP client for PDF downloads
  - rich: Terminal output formatting (progress bars, tables, status)
- **Secrets**:
  - LLM API key (provider-dependent, e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY) — required
  - S2_API_KEY — optional (higher rate limits with key, works without)

### Data Flow
Research Questions → [Query Generation] → [Paper Discovery] → [Metadata Enrichment] → [LLM Analysis] → [Ranking] → [Export]
- **Trigger**: Manual (CLI command)
- **Volume**: ~50–200 candidate papers per run, ~20–50 analyzed in depth, Top-N exported

### External Services
| Service | Auth | Rate Limit | Purpose |
|---------|------|------------|---------|
| Semantic Scholar API | API Key (optional) | 1 RPS authenticated, shared pool unauthenticated | Paper search, metadata, OA-PDF links |
| LLM Provider (via LiteLLM) | API Key (required) | Provider-dependent | Query generation, abstract screening, paper analysis, synthesis |

### Data Model
- **Input**: List of research questions (strings)
- **Intermediate State** (JSON, resumable):
  - Generated facets and search queries
  - Candidate papers with metadata (title, abstract, authors, year, citations, venue, DOI, PDF URL)
  - Screening scores (Stage A)
  - Full analysis results (Stage B)
- **Output**:
  - report.md — Main report (questions, search strategy, top-N papers with analysis, synthesis with research gaps)
  - paper_analyses.md — Detailed analysis of all screened papers
  - references.bib — BibTeX for top-N papers
  - references.ris — RIS format (Zotero, Mendeley, Citavi import)
  - papers/ — Downloaded PDFs of top-N open access papers
  - data.json — Machine-readable export of all metadata + analyses

### Components
| Component | Purpose | Priority |
|-----------|---------|----------|
| cli.py | Typer CLI with `run`, `resume`, `config` commands | MVP |
| config.py | Pydantic Settings — all parameters configurable via TOML file + CLI flags + ENV | MVP |
| models.py | Pydantic models: Paper, Analysis, SearchQuery, Facet, PipelineState | MVP |
| pipeline.py | Orchestrator — runs stages sequentially, saves state after each stage | MVP |
| stages/query_gen.py | Stage 1: LLM generates facets + search queries from research questions | MVP |
| stages/discovery.py | Stage 2: Semantic Scholar API search, deduplication by DOI/Corpus-ID | MVP |
| stages/enrichment.py | Stage 3: Fetch full metadata for all candidates via S2 API | MVP |
| stages/analysis.py | Stage 4: Two-phase LLM analysis (A: abstract screening, B: extended with PDF text) | MVP |
| stages/ranking.py | Stage 5: Multi-criteria ranking (relevance score → citations → year) | MVP |
| stages/export.py | Stage 6: Generate report.md, paper_analyses.md, references.bib, references.ris, data.json, download PDFs | MVP |
| pdf.py | PDF text extraction — page heuristic: first N + last M pages | MVP |
| prompts/query_gen.md | Prompt template for facet + query generation | MVP |
| prompts/screening.md | Prompt template for abstract screening (Stage A) | MVP |
| prompts/analysis.md | Prompt template for extended analysis (Stage B) | MVP |
| prompts/synthesis.md | Prompt template for literature synthesis in report | MVP |

### Pipeline Stages Detail

**Stage 1 — Query Generation**
LLM receives research questions, derives thematic facets, generates 2–3 targeted search queries per facet. Output: list of Facet objects with queries.

**Stage 2 — Paper Discovery**
Each query hits Semantic Scholar relevance search endpoint. Results deduplicated by paperId/DOI. Output: candidate pool (typically 50–200 papers).

**Stage 3 — Metadata Enrichment**
Batch fetch via S2 API: title, abstract, authors, year, citationCount, venue, openAccessPdf, externalIds (DOI). Output: enriched Paper objects.

**Stage 4A — Abstract Screening**
Each paper's abstract + metadata sent to LLM. Returns relevance score (0–100). Papers below threshold (default: 40) are filtered out. Fast, cheap (short prompts).

**Stage 4B — Extended Analysis**
For papers passing screening: download PDF, extract first 4 + last 2 pages via pypdf, send to LLM with full analysis prompt. Returns: summary, key_findings, methodology, relevance_score (refined), relevance_rationale.

**Stage 5 — Ranking**
Sort by: relevance_score (desc) → citationCount (desc) → year (desc). Apply top_n cutoff.

**Stage 6 — Export**
Generate all output files. report.md includes a final LLM-generated synthesis section analyzing consensus, contradictions, and research gaps across top-N papers.

## Objectives
### MVP (v0.1)
- [ ] Full pipeline runs end-to-end: questions in → report + PDFs + BibTeX out
- [ ] All 6 stages implemented and working
- [ ] Configuration via TOML file + CLI flags
- [ ] Resume interrupted runs via --resume flag
- [ ] Works with at least OpenAI and Anthropic via LiteLLM
- [ ] Installable via pip install (proper pyproject.toml with entry point)
- [ ] README with quickstart, usage examples, configuration reference
- [ ] Tests for core logic (models, ranking, export formatting)
- [ ] CI via GitHub Actions (nox: lint + typecheck + test)

### Non-Goals
- GUI / Web interface
- NotebookLM integration
- Citation graph analysis
- Full-text PDF analysis (MVP uses page heuristic)
- Configurable analysis schema (MVP uses fixed schema)
- Section-aware PDF parsing (GROBID)
- Multi-source search (OpenAlex) — S2 only for MVP

## Constraints
- Semantic Scholar API: 1 RPS with key, respect rate limits. Use async batch where possible.
- LLM costs: Two-phase analysis minimizes tokens. Abstract screening is cheap (~200 tokens/paper). Extended analysis only for papers above threshold.
- PDF downloads: Only open access papers. Fail gracefully if PDF unavailable.
- License compatibility: All dependencies must be MIT/BSD/Apache-2.0 compatible. No AGPL.

## Setup
- **Category**: Open Source
- **Git Remote**: https://github.com/SilasPignotti/litresearch
- **License**: MIT
- **Release**: PyPI via GitHub Actions (Trusted Publisher, tag-triggered)
- **Versioning**: SemVer, start at 0.1.0, manual bumping + git-cliff for changelogs
- **Python**: 3.12
- **Package Manager**: uv
- **Quality**: nox (sessions: lint, typecheck, test) + ruff + pyright + pytest
- **CI**: GitHub Actions running nox on push/PR

## Context
- **Key Docs**:
  - Semantic Scholar API: https://api.semanticscholar.org/api-docs/
  - semanticscholar Python client: https://semanticscholar.readthedocs.io/
  - LiteLLM: https://docs.litellm.ai/docs/
  - Typer: https://typer.tiangolo.com/
  - pypdf: https://pypdf.readthedocs.io/
- **Decisions**:
  - LiteLLM over direct API calls — provider-agnostic is critical for open source adoption
  - pypdf over PyMuPDF — AGPL license incompatible with MIT project
  - JSON state over SQLite — simpler for MVP, SQLite as future enhancement
  - Page heuristic (first 4 + last 2 pages) over section-aware parsing — no external services needed
  - Prompts as markdown files — editable without code changes, version-controlled
  - Dual interface (CLI + Python API) — Typer for CLI, underlying functions importable as library

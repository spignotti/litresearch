# litresearch
[![CI](https://github.com/spignotti/litresearch/actions/workflows/ci.yml/badge.svg)](https://github.com/spignotti/litresearch/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/litresearch.svg)](https://pypi.org/project/litresearch/)

CLI tool that automates literature research from research questions to curated,
ranked, and exported paper sets with structured reports.

## Overview
- Generates search facets and academic queries from one or more research questions
- Discovers candidates from Semantic Scholar and OpenAlex
- Screens and analyzes papers with an LLM through LiteLLM
- Supports citation graph expansion for frequently referenced works
- Ranks papers and exports reports, references, JSON data, PDFs, and metrics
- Supports robust resume via a saved `state.json`

## What's New in v1.0.0

### Multi-source discovery (S2 + OpenAlex)
- Use `discovery_sources = ["s2", "openalex"]` for broader coverage.
- Candidates are deduplicated across sources and source provenance is tracked.

### Citation graph expansion
- Optional expansion stage adds highly cross-referenced papers after ranking.
- Configure with `expand_citations` and `min_cross_refs`.

### Zotero export
- Export top papers to Zotero user or group libraries.
- Supports collection assignment, tags, and PDF attachment when available.

### PDF injection
- Bring your own PDFs with `--inject-pdfs` or `inject_pdf_dir`.
- Match files by `{paper_id}.pdf` or DOI-based filenames.

### Run metrics and telemetry
- Every run writes `metrics.json` with stage timings and aggregate counts.
- Includes source breakdown plus PDF availability and usage metrics.

### Resume behavior improvements
- Improved resume reliability from `state.json` checkpoints.
- Safer state persistence with atomic writes.

### Token-budgeted PDF extraction
- Configurable extraction strategy supports token budgets for LLM context limits.
- Falls back gracefully when PDFs are unavailable or extraction is limited.

## Installation
```bash
uv pip install litresearch
```

For local development:

```bash
uv sync
uv run nox
```

## Quickstart
1. Set an LLM API key for a LiteLLM-supported provider:

```bash
export OPENAI_API_KEY=your_key_here
# or
export ANTHROPIC_API_KEY=your_key_here
```

2. Optionally set a Semantic Scholar key for better rate limits:

```bash
export S2_API_KEY=your_key_here
```

3. Copy the example config and tune defaults:

```bash
cp litresearch.toml.example litresearch.toml
```

4. Run the pipeline:

```bash
litresearch run "What is the impact of large language models on software engineering?"
```

5. Inspect the output directory:

```text
output/
  report.md
  paper_analyses.md
  references.bib
  references.ris
  data.json
  metrics.json
  papers/
  state.json
```

## Usage
Run one or more research questions:

```bash
litresearch run \
  "How do large language models affect developer productivity?" \
  "What evidence exists about code quality impacts?"
```

Override settings from the CLI:

```bash
litresearch run \
  "How do LLMs affect software engineering?" \
  --model anthropic/claude-sonnet-4-20250514 \
  --top-n 10 \
  --threshold 50 \
  --output-dir runs/llm-se \
  --overwrite
```

Resume an interrupted run:

```bash
litresearch resume output/state.json
```

Inject local PDFs for papers you already have:

```bash
litresearch run "Your research question" --inject-pdfs /path/to/pdfs
```

Inspect current configuration:

```bash
litresearch config
```

## Configuration
Settings load in this order:
1. CLI flags
2. Environment variables
3. `litresearch.toml`
4. Built-in defaults

Supported environment variables:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENROUTER_API_KEY`
- `S2_API_KEY`
- `ZOTERO_API_KEY`
- `S2_TIMEOUT`
- `S2_REQUESTS_PER_SECOND`
- `SCREENING_SELECTION_MODE`
- `SCREENING_TOP_PERCENT`
- `SCREENING_TOP_K`
- `SCREENING_THRESHOLD`

Start from the full example config:

```bash
cp litresearch.toml.example litresearch.toml
```

Key options include:

```toml
default_model = "openai/gpt-4o-mini"
llm_timeout = 120
max_retries = 3
retry_base_delay = 1.0
discovery_sources = ["s2"]
screening_selection_mode = "top_percent"
screening_top_percent = 0.3
screening_threshold = 60
top_n = 20
max_results_per_query = 20
expand_citations = false
min_cross_refs = 3
zotero_export = false
s2_timeout = 10
s2_requests_per_second = 1.0
pdf_extraction_mode = "budget"
pdf_token_budget = 4000
pdf_first_pages = 4
pdf_last_pages = 2
abstract_fallback = true
# inject_pdf_dir = "/path/to/pdfs"
output_dir = "output"
```

Screening selection modes:
- `top_percent` (default): deep-analyze the top share of screened papers globally
- `top_k`: deep-analyze the top K screened papers globally
- `threshold`: deep-analyze papers scoring `>= screening_threshold`

Semantic Scholar tuning:
- `s2_timeout`: request timeout in seconds
- `s2_requests_per_second`: global request rate cap across S2 endpoints

Discovery tuning:
- `discovery_sources`: choose `s2`, `openalex`, or both
- `openalex_email`: optional email for OpenAlex polite pool rate limits

Citation expansion tuning:
- `expand_citations`: enable or disable expansion stage
- `min_cross_refs`: minimum citation graph references to include

Zotero export tuning:
- `zotero_export`: enable export integration
- `zotero_library_id`, `zotero_library_type`, `zotero_collection_key`, `zotero_tag`

## Output Files
- `report.md`: main literature review report with research questions, search summary, top papers, and synthesis
- `paper_analyses.md`: detailed per-paper analysis for all analyzed papers
- `references.bib`: BibTeX for ranked papers when citation data is available
- `references.ris`: RIS export for citation managers
- `data.json`: machine-readable export of the pipeline state
- `metrics.json`: per-stage timings and aggregate run metrics
- `papers/`: downloaded open-access PDFs for ranked papers
- `state.json`: resumable pipeline checkpoint

## Development
```bash
uv run nox
uv run litresearch --help
```

## Status
`v1.0.0` delivers a production-ready core workflow for automated literature research,
including multi-source discovery, ranking, export, and operational telemetry.

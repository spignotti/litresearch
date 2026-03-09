# litresearch
[![CI](https://github.com/spignotti/litresearch/actions/workflows/ci.yml/badge.svg)](https://github.com/spignotti/litresearch/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/litresearch.svg)](https://pypi.org/project/litresearch/)

CLI tool that automates literature research from research questions to curated,
ranked, and exported paper sets with structured reports.

## Overview
- Generates search facets and academic queries from one or more research questions
- Searches Semantic Scholar for candidate papers
- Screens and analyzes papers with an LLM through LiteLLM
- Ranks papers and exports reports, references, JSON data, and PDFs
- Supports resume via a saved `state.json`

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

3. Run the pipeline:

```bash
litresearch run "What is the impact of large language models on software engineering?"
```

4. Inspect the output directory:

```text
output/
  report.md
  paper_analyses.md
  references.bib
  references.ris
  data.json
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
  --output-dir runs/llm-se
```

Resume an interrupted run:

```bash
litresearch resume output/state.json
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

Example `litresearch.toml`:

```toml
default_model = "openai/gpt-4o-mini"
screening_threshold = 40
top_n = 20
max_results_per_query = 20
pdf_first_pages = 4
pdf_last_pages = 2
output_dir = "output"
```

## Output Files
- `report.md`: main literature review report with research questions, search summary, top papers, and synthesis
- `paper_analyses.md`: detailed per-paper analysis for all analyzed papers
- `references.bib`: BibTeX for ranked papers when citation data is available
- `references.ris`: RIS export for citation managers
- `data.json`: machine-readable export of the pipeline state
- `papers/`: downloaded open-access PDFs for ranked papers
- `state.json`: resumable pipeline checkpoint

## Development
```bash
uv run nox
uv run litresearch --help
```

## Status
This is an MVP-oriented proof of concept intended to answer one question clearly:
is the end-to-end literature research workflow useful enough to keep investing in?

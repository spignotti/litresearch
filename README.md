# litresearch

CLI tool that automates literature research from research questions to curated,
ranked, and exported paper sets with structured reports.

## Overview
- Automates discovery, screening, analysis, ranking, and export steps.
- Targets a CLI-first workflow with an importable Python API.
- Uses Semantic Scholar for paper metadata and LiteLLM for provider-agnostic LLM access.

## Planned Architecture
- Framework: Typer CLI with package modules under `src/litresearch/`
- Core dependencies: LiteLLM, Semantic Scholar client, Pydantic, httpx, pypdf, Rich
- Outputs: Markdown reports, bibliographic exports, downloaded PDFs, and JSON pipeline state

## Development
```bash
uv sync
uv run nox
uv run litresearch --help
```

## Status
This repository currently contains project scaffolding only. Product logic will be added in later planning and task steps.

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-09

### Added
- **Multi-source discovery**: Support for both Semantic Scholar and OpenAlex APIs
  - Configurable discovery sources via `discovery_sources` setting
  - OpenAlex adapter with field mapping
  - Global deduplication using DOI match and fuzzy title matching
  - Source tracking (s2, openalex, both, citation_expansion)

- **Citation graph expansion**: Optional post-ranking stage to discover frequently referenced works
  - Configurable via `expand_citations` and `min_cross_refs` settings
  - Adds cross-referenced papers as recommended reading

- **Zotero integration**: Export top papers directly to Zotero library
  - Support for user and group libraries
  - Automatic PDF attachment
  - Custom tagging and collection assignment
  - Configurable via `zotero_*` settings

- **Run-quality telemetry**: Comprehensive metrics collection
  - `RunMetrics` and `StageMetrics` models
  - Per-stage timing, input/output counts, error tracking
  - Aggregate statistics (candidates, screened, analyzed, exported)
  - Source breakdown and PDF status tracking
  - Written to `metrics.json` in output directory

- **Manual PDF injection**: Support for providing your own PDFs
  - `--inject-pdfs` CLI flag
  - Configurable via `inject_pdf_dir` setting
  - Matching by paper_id or DOI filename
  - Useful for papers behind paywalls

- **Token-budgeted PDF extraction**: Intelligent text extraction
  - Replaces fixed first/last pages heuristic
  - Keyword-based page scoring
  - Configurable token budget
  - Falls back gracefully when extraction fails

- **Abstract-fallback screening**: Multi-signal screening for papers without abstracts
  - Uses title, venue, citation count, year, and PDF excerpts
  - Conservative scoring bias toward inclusion
  - Dedicated `screening_fallback.md` prompt

- **Robust error handling**: Resilience against external failures
  - `parse_llm_json()` helper with comprehensive validation
  - `retry_with_backoff()` decorator for API calls
  - Configurable retry settings (`max_retries`, `retry_base_delay`)
  - Graceful degradation when LLM returns malformed JSON

- **Security improvements**:
  - Path sanitization via `safe_filename()` utility
  - Atomic state persistence using temp file + os.replace

### Changed
- **PDF tracking**: Replaced `pdf_downloaded: bool` with richer fields
  - `pdf_path: str | None` - relative path to PDF
  - `pdf_status: Literal["not_attempted", "downloaded", "unavailable", "user_provided"]`
  - `data_completeness: Literal["full", "abstract_only", "metadata_only"]`

- **Version source**: Single-source version via `importlib.metadata`
  - Removed hardcoded version from `__init__.py`
  - Version now sourced from `pyproject.toml`

- **Configuration**: Added `litresearch.toml.example` with all new options
  - Renamed existing `litresearch.toml` to example file
  - Real config files now gitignored

### Fixed
- **Resume bug**: Fixed crash when resuming from `current_stage="start"`
- **State persistence**: Atomic writes prevent state corruption on interrupt
- **JSON parsing**: Proper handling of missing keys and validation errors in LLM responses
- **Path traversal**: Sanitized paper_id usage in filenames

### Dependencies
- Added `pyalex>=0.15` for OpenAlex integration
- Added `pyzotero>=1.6` for Zotero export
- Added optional `rapidfuzz` dependency for fuzzy title matching (falls back to difflib)

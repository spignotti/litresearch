# Feature: v0.1.0 Release Polish

## Context
Full repo scan following the first successful end-to-end smoke test run.
Goal: identify everything needed to turn a working MVP into a publishable v0.1.0.

## Current State
- Nox result: **3/3 sessions passed** — lint, typecheck, 11 tests. Clean baseline.
- Smoke test result: 1 research question → 4 facets → 8 queries → 35 candidates → 35 screened → 32 analyzed → 5 exported
- Discovery: 850s (14+ min) — primary performance problem
- Analysis: 225s — acceptable for 32 papers with PDF extraction

## Requirements

### Critical — must fix before publish

- [ ] **[Critical]** `src/litresearch/stages/analysis.py:35,63` — `json.loads(response)` in both `_screen_paper` and `_analyze_paper` is unguarded. If the LLM returns malformed JSON, this raises `json.JSONDecodeError` which is not caught, crashing the entire analysis stage.
  → Wrap in `try/except json.JSONDecodeError` in each helper; return `None` on parse failure with a warning print.

- [ ] **[Critical]** `src/litresearch/stages/discovery.py:31` — `SemanticScholar()` is instantiated with no timeout or retry config. The library's default retry logic caused 14 minutes of discovery time for 8 queries.
  → Pass `timeout=10` and `retry=False` to the constructor. Expose as a config setting.

- [ ] **[Critical]** `src/litresearch/stages/analysis.py` / `src/litresearch/stages/export.py` — PDFs are downloaded twice: once in analysis and once in export.
  → During analysis, if the download succeeds, save the bytes to `papers/` immediately and mark `pdf_downloaded=True` on the paper in state. Export stage skips already-downloaded papers.

### Major — fix before publish

- [ ] **[Major]** `src/litresearch/cli.py:21-33` — `_build_settings` mutates a `Settings` instance after construction.
  → Replace with `Settings(**{k: v for k, v in overrides.items() if v is not None})` so the object is built correctly in one call.

- [ ] **[Major]** `src/litresearch/stages/export.py:75` — running `litresearch run` into an already-populated output directory silently overwrites files with no warning.
  → Detect existing output dir content at pipeline start. Either auto-increment the directory name (e.g. `output-smoke-2`) or print a clear warning and require `--overwrite` to proceed.

- [ ] **[Major]** `src/litresearch/stages/analysis.py:72` — papers with no abstract are skipped silently before screening. No `ScreeningResult` is written for them.
  → Write a `ScreeningResult` with `relevance_score=0` and `rationale="no abstract available"` for skipped papers.

- [ ] **[Major]** `src/litresearch/stages/query_gen.py:11` — `call_llm` is called without a try/except. If query generation fails, there's no way to resume past this.
  → Wrap in try/except `LLMError`; re-raise with a clear message.

- [ ] **[Major]** `litresearch.toml` is committed to the repo. New users will inherit this config silently.
  → Rename to `litresearch.toml.example` and add `litresearch.toml` to `.gitignore`.

- [ ] **[Major]** `src/litresearch/stages/export.py` — HTML entities in S2 metadata are passed through verbatim.
  → Unescape HTML entities in `Paper.from_s2()` using `html.unescape()` on `title`, `venue`, and `abstract` fields.

- [ ] **[Major]** Test coverage has zero stage-level tests. All six pipeline stages are untested.
  → Add at minimum: `test_stages_query_gen.py`, `test_stages_screening.py`, `test_stages_discovery.py` with mocks.

### Minor — polish before publish

- [ ] **[Minor]** `src/litresearch/stages/enrichment.py:38` — `BATCH_SIZE = 500` is a magic number.
  → Add an inline comment: `# S2 /papers batch endpoint limit`.

- [ ] **[Minor]** `src/litresearch/pipeline.py` — no run summary is printed at the end.
  → Print a summary block after the last stage: total elapsed, counts per stage, output path.

- [ ] **[Minor]** `src/litresearch/config.py` — `screening_threshold` default is `40` but documentation describes threshold behavior without specifying the default clearly.
  → Set default to `60` (matches the smoke test calibration). Add a comment: `# 0-100; papers scoring below this are filtered before full analysis`.

## Pre-publish Checklist

- [ ] `litresearch.toml` → `.gitignore` + `litresearch.toml.example`
- [ ] `README.md` — document `uv pip install litresearch`
- [ ] `README.md` — document `litresearch.toml.example` → copy and configure
- [ ] `README.md` — document resume behavior and output directory structure
- [ ] Bump `__version__` to `0.1.0` when ready to tag
- [ ] Confirm `pyproject.toml` classifiers and description are publication-ready
- [ ] Tag `v0.1.0` and publish to PyPI via `uv build && uv publish`
- [ ] GitHub: add a `v0.1.0` release with changelog notes
- [ ] Add `CHANGELOG.md` (even just a minimal one-entry file)

## Validation

Run `uv run nox` before each commit. All sessions must pass.

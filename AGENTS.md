# litresearch

CLI tool that automates literature research from research questions to curated,
ranked, and exported paper sets with structured reports.

## Repository Category

`oss` — public, publishable, reviewable.

- always work on a feature branch, never directly on `main`
- conventional commits, PR flow, squash merge in GitHub UI
- keep README, packaging metadata, and release hygiene public-facing and intentional
- run `/oss-setup` once after `/python-init` to apply CI, release workflow, and license

## Tech Stack

- Python 3.12
- uv — package management
- ruff — linting and formatting
- pyright — type checking
- pytest + pytest-cov — tests with coverage
- nox — validation entrypoint
- Typer — CLI framework
- LiteLLM, Semantic Scholar client, Pydantic, httpx, pypdf, Rich

## Project Type

`cli` — command-line interface tool

## Structure

```
src/litresearch/    # main package
  cli.py            # Typer CLI entrypoint
  config.py         # Pydantic settings
  pipeline.py       # Orchestrator
  stages/           # Pipeline stages
  models.py         # Data models
  prompts/          # LLM prompts
tests/              # tests
```

## Validation

- `uv run nox` — full validation gate; run before every commit
- `nox -s lint` — docs, config, comment-only changes
- `nox -s lint typecheck` — structural changes (new modules, imports, type signatures)
- `nox -s lint typecheck test` — logic or behavior changes
- `nox -s ci` — CI equivalent; mirrors what GitHub Actions runs

## Python Stack

- `uv` — package and environment management
- `ruff` — linting and formatting
- `pyright` — type checking
- `pytest` — tests
- `nox` — validation entrypoint; run `uv run nox` before every commit

## Conventions

- Keep scaffold files minimal until /plan defines implementation work.
- Use `src/` layout for all package code.
- Prefer small, typed modules with fail-fast validation.
- Keep CLI wiring thin; business logic belongs in separate modules.
- Follow existing patterns before introducing new ones
- Keep the README accurate and presentable

## Library Documentation

Context7 MCP is available in this project. When working with any external library, use it to fetch current, version-specific documentation rather than relying on training data.

## Known Constraints

- Semantic Scholar and LLM provider details stay in configuration, not hard-coded
- Multi-stage pipeline design: "download once, cache path in state" pattern required
- SemanticScholar client requires explicit `timeout=` and `retry=False` configuration to avoid aggressive default retries
- Smoke-test config (`litresearch.toml`) must not be committed — use `litresearch.toml.example`
- Test coverage is minimal (11 tests, no stage-level tests) — see feature.md for improvement roadmap

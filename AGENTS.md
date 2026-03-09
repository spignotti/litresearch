# litresearch

## Overview
CLI-first Python package for automated literature research workflows. The scaffold
supports a Typer CLI, importable package code, and standard OSS tooling.

## Tech Stack
- Language: Python 3.12
- Framework: Typer
- Core dependencies: LiteLLM, Semantic Scholar client, Pydantic, httpx, pypdf, Rich
- Tooling: uv, Ruff, Pyright, Pytest, Nox, GitHub Actions

## Directory Structure
src/
  litresearch/      Python package and CLI entrypoints

tests/
  unit/             Fast unit tests
  integration/      Integration-level CLI checks

docs/
  decisions/        ADRs and design notes

## Conventions
- Keep scaffold files minimal until /plan defines implementation work.
- Use `src/` layout for all package code.
- Prefer small, typed modules with fail-fast validation.
- Keep CLI wiring thin; business logic belongs in separate modules.

## Architecture Decisions
- Typer provides the public CLI surface.
- Pydantic settings handle environment-backed configuration.
- Nox is the single entrypoint for lint, typecheck, and test workflows.
- GitHub Actions should mirror local `uv run nox` behavior.

## Known Constraints
- This repo is scaffold-only at init time. Pipeline stages and prompts are not implemented here.
- Semantic Scholar and LLM provider details stay in configuration, not hard-coded in the scaffold.

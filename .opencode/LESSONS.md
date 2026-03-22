# Project Lessons

Project-specific learnings for this repository. Run `/lessons` to curate entries, promote cross-project patterns to the global lessons file, and promote standing rules to `AGENTS.md`.

Entry format: `- [YYYY-MM-DD] <what was tricky or wrong> → <correct approach>`

---

## Project Decisions

<!-- one-off architectural choices, constraints, workarounds specific to this project -->

## Tooling and Environment

<!-- project-specific tool behavior, config quirks, environment setup gotchas -->

- [2026-03-09] `SemanticScholar()` without explicit `timeout=` and `retry=False` uses aggressive default retries (up to 10×, 30s waits on 429) — caused 14-min discovery for 8 queries. Always configure both on construction.
- [2026-03-09] `pydantic-settings` TOML support requires overriding `settings_customise_sources()` to include `TomlConfigSettingsSource`; setting `toml_file=` in `model_config` alone does nothing.
- [2026-03-09] For multi-stage pipelines that download files at one stage and re-use them at another, design "download once, cache path in state" from the start — retrofitting requires touching multiple stages and the state model.
- [2026-03-09] `uv run <cmd>` in a project repo keeps reinstalling the local package as editable, overriding a clean non-editable install. Workaround: `uv pip install . && uv run --no-project <cmd>`. This is a uv project-detection behavior, not a package bug.
- [2026-03-09] Smoke-test config (litresearch.toml) must not be committed to git — users inherit it silently and could accidentally commit secrets. Use `litresearch.toml.example` + gitignore pattern.

## Recurring Issues

<!-- patterns that keep coming up in this project — candidates for promotion to global lessons -->

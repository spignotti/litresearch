# Project State

## Current Focus
- Validate installed `litresearch` behavior with low-cost end-to-end smoke runs.

## Active Work
- None.

## Key Decisions
- [2026-04-11] v1.0.0 release blockers were resolved (security fixes, CLI fix, settings wiring, rate limiting, tests added).
- [2026-04-20] Use a temporary workspace with constrained runtime settings (`max_results_per_query=5`, `screening_selection_mode=top_k`, `screening_top_k=3`, `top_n=5`) for low-cost verification before broader test campaigns.

## Lessons
- [2026-04-20] `--stop-after-screening` pause + `resume` currently re-runs full screening in `analysis` stage instead of resuming post-screening, which increases LLM cost and time for pause/resume workflows.
- [2026-04-20] Resume writes a new `metrics.json` run timeline from the resume invocation, so pre-pause stage metrics are not preserved in the final metrics artifact.

## Next Steps
- Add a dedicated post-screening checkpoint state so `resume` can skip re-screening.
- Preserve/merge metrics across paused and resumed segments.
- Add a configurable hard cap for total generated queries or total candidates to keep cost predictable.

## Blocked
- None.

"""Pipeline orchestration for litresearch."""

import time
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from litresearch.config import Settings
from litresearch.models import PipelineState
from litresearch.stages import analysis, discovery, enrichment, export, query_gen, ranking

console = Console()

# Each stage module exposes a shared `run(state, settings)` function.
STAGES = {
    "query_gen": query_gen.run,
    "discovery": discovery.run,
    "enrichment": enrichment.run,
    "analysis": analysis.run,
    "ranking": ranking.run,
    "export": export.run,
}
STAGE_ORDER = list(STAGES)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def run_pipeline(
    questions: list[str],
    settings: Settings,
    resume_path: Path | None = None,
    overwrite: bool = False,
) -> PipelineState:
    """Run the configured pipeline from scratch or from a saved state."""
    if resume_path is not None:
        state = PipelineState.load(resume_path)
        output_dir = Path(state.output_dir)
        start_index = STAGE_ORDER.index(state.current_stage) + 1
    else:
        output_dir = Path(settings.output_dir)
        if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
            base_name = output_dir.name
            parent = output_dir.parent
            counter = 2
            while output_dir.exists() and any(output_dir.iterdir()):
                output_dir = parent / f"{base_name}-{counter}"
                counter += 1
            console.print(f"[yellow]Output directory already exists. Using:[/yellow] {output_dir}")
        state = PipelineState(
            questions=questions,
            current_stage="start",
            output_dir=str(output_dir),
            created_at=_timestamp(),
            updated_at=_timestamp(),
        )
        start_index = 0

    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "state.json"

    for stage_name in STAGE_ORDER[start_index:]:
        console.print(f"[bold blue]Running stage:[/bold blue] {stage_name}")
        started = time.perf_counter()
        stage_runner = STAGES[stage_name]
        try:
            state = stage_runner(state, settings)
            state = state.model_copy(update={"updated_at": _timestamp()})
            state.save(state_path)
        except Exception as exc:  # noqa: BLE001
            failed_state = state.model_copy(update={"updated_at": _timestamp()})
            failed_state.save(state_path)
            console.print(f"[red]Stage failed:[/red] {stage_name} ({exc})")
            console.print(f"Resume with: litresearch resume {state_path}")
            raise
        elapsed = time.perf_counter() - started
        console.print(f"[green]Completed[/green] {stage_name} in {elapsed:.2f}s")

    return state

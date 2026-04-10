"""Pipeline orchestration for litresearch."""

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from litresearch.config import Settings
from litresearch.models import PipelineState, RunMetrics, StageMetrics
from litresearch.stages import (
    analysis,
    citation_expansion,
    discovery,
    enrichment,
    export,
    query_gen,
    ranking,
)
from litresearch.stages.analysis import PauseForPDFsError

console = Console()

# Each stage module exposes a shared `run(state, settings)` function.
STAGES = {
    "query_gen": query_gen.run,
    "discovery": discovery.run,
    "enrichment": enrichment.run,
    "analysis": analysis.run,
    "ranking": ranking.run,
    "citation_expansion": citation_expansion.run,
    "export": export.run,
}
STAGE_ORDER = list(STAGES)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _write_metrics(output_dir: Path, metrics: RunMetrics) -> None:
    (output_dir / "metrics.json").write_text(
        metrics.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


def _stage_count(stage_name: str, state: PipelineState) -> int:
    if stage_name == "query_gen":
        return len(state.search_queries)
    if stage_name in {"discovery", "enrichment", "citation_expansion"}:
        return len(state.candidates)
    if stage_name == "analysis":
        return len(state.analyses)
    if stage_name == "ranking":
        return len(state.ranked_paper_ids)
    if stage_name == "export":
        return len(state.ranked_paper_ids)
    return 0


def _populate_aggregate_metrics(metrics: RunMetrics, state: PipelineState) -> RunMetrics:
    source_counts: dict[str, int] = {}
    for paper in state.candidates:
        source_counts[paper.source] = source_counts.get(paper.source, 0) + 1

    return metrics.model_copy(
        update={
            "total_candidates": len(state.candidates),
            "total_screened": len(state.screening_results),
            "total_analyzed": len(state.analyses),
            "total_exported": len(state.ranked_paper_ids),
            "citation_expanded": source_counts.get("citation_expansion", 0),
            "sources": source_counts,
            "pdfs_downloaded": sum(
                1 for paper in state.candidates if paper.pdf_status == "downloaded"
            ),
            "pdfs_user_provided": sum(
                1 for paper in state.candidates if paper.pdf_status == "user_provided"
            ),
            "pdfs_unavailable": sum(
                1 for paper in state.candidates if paper.pdf_status == "unavailable"
            ),
        }
    )


def run_pipeline(
    questions: list[str],
    settings: Settings,
    resume_path: Path | None = None,
    overwrite: bool = False,
    inject_pdfs_dir: Path | None = None,
    stop_after_screening: bool = False,
) -> PipelineState:
    """Run the configured pipeline from scratch or from a saved state."""
    start_time = time.perf_counter()
    started_at = _timestamp()

    if resume_path is not None:
        state = PipelineState.load(resume_path)
        output_dir = Path(state.output_dir)
        if state.current_stage == "start":
            start_index = 0
        else:
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
    metrics = RunMetrics(run_id=f"run-{uuid.uuid4().hex[:12]}", started_at=started_at)
    effective_inject_pdfs_dir = inject_pdfs_dir
    if effective_inject_pdfs_dir is None and settings.inject_pdf_dir:
        effective_inject_pdfs_dir = Path(settings.inject_pdf_dir)

    for stage_name in STAGE_ORDER[start_index:]:
        console.print(f"[bold blue]Running stage:[/bold blue] {stage_name}")
        started = time.perf_counter()
        stage_metrics = StageMetrics(
            name=stage_name,
            started_at=_timestamp(),
            input_count=_stage_count(stage_name, state),
        )
        stage_runner = STAGES[stage_name]
        try:
            if stage_name == "analysis":
                state = stage_runner(
                    state,
                    settings,
                    inject_pdfs_dir=effective_inject_pdfs_dir,
                    stop_after_screening=stop_after_screening,
                )
            elif stage_name == "export":
                state = stage_runner(state, settings, run_metrics=metrics)
            else:
                state = stage_runner(state, settings)
            stage_metrics = stage_metrics.model_copy(
                update={
                    "completed_at": _timestamp(),
                    "duration_seconds": time.perf_counter() - started,
                    "output_count": _stage_count(stage_name, state),
                }
            )
            metrics = metrics.model_copy(update={"stages": [*metrics.stages, stage_metrics]})
            state = state.model_copy(update={"updated_at": _timestamp()})
            state.save(state_path)
            metrics = _populate_aggregate_metrics(metrics, state)
            _write_metrics(output_dir, metrics)
        except PauseForPDFsError:
            # Not a failure - user chose to pause for manual PDF injection
            # Save state at screening checkpoint
            checkpoint_state = state.model_copy(
                update={
                    "updated_at": _timestamp(),
                }
            )
            checkpoint_state.save(state_path)
            console.print("\n[bold yellow]Pipeline paused at screening checkpoint.[/bold yellow]")
            console.print(f"State saved to: {state_path}")
            return state  # Return current state
        except Exception as exc:  # noqa: BLE001
            stage_metrics = stage_metrics.model_copy(
                update={
                    "completed_at": _timestamp(),
                    "duration_seconds": time.perf_counter() - started,
                    "error_count": 1,
                }
            )
            metrics = metrics.model_copy(update={"stages": [*metrics.stages, stage_metrics]})
            metrics = _populate_aggregate_metrics(metrics, state)
            _write_metrics(output_dir, metrics)
            failed_state = state.model_copy(update={"updated_at": _timestamp()})
            failed_state.save(state_path)
            console.print(f"[red]Stage failed:[/red] {stage_name} ({exc})")
            console.print(f"Resume with: litresearch resume {state_path}")
            raise
        elapsed = time.perf_counter() - started
        console.print(f"[green]Completed[/green] {stage_name} in {elapsed:.2f}s")

    metrics = _populate_aggregate_metrics(metrics, state)
    metrics = metrics.model_copy(
        update={
            "completed_at": _timestamp(),
            "total_duration_seconds": time.perf_counter() - start_time,
        }
    )
    _write_metrics(output_dir, metrics)

    # Print run summary
    console.print("\n[bold]Run Summary[/bold]")
    console.print(f"  Total time: {metrics.total_duration_seconds:.1f}s")
    console.print(f"  Candidates: {metrics.total_candidates}")
    console.print(f"  Screened: {metrics.total_screened}")
    console.print(f"  Analyzed: {metrics.total_analyzed}")
    console.print(f"  Exported: {metrics.total_exported}")
    console.print(f"  Output: {state.output_dir}")

    return state

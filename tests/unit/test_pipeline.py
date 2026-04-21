from pathlib import Path

from litresearch import pipeline
from litresearch.config import Settings
from litresearch.models import PipelineState, RunMetrics, StageMetrics


def test_run_pipeline_auto_increments_non_empty_output_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "STAGE_ORDER", [])

    base_output = tmp_path / "output"
    base_output.mkdir()
    (base_output / "existing.txt").write_text("data", encoding="utf-8")

    state = pipeline.run_pipeline(
        questions=["q"],
        settings=Settings(output_dir=str(base_output)),
    )

    assert state.output_dir == str(tmp_path / "output-2")
    assert (tmp_path / "output-2").exists()


def test_run_pipeline_keeps_output_dir_when_overwrite_enabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "STAGE_ORDER", [])

    base_output = tmp_path / "output"
    base_output.mkdir()
    (base_output / "existing.txt").write_text("data", encoding="utf-8")

    state = pipeline.run_pipeline(
        questions=["q"],
        settings=Settings(output_dir=str(base_output)),
        overwrite=True,
    )

    assert state.output_dir == str(base_output)


def test_run_pipeline_keeps_empty_existing_output_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "STAGE_ORDER", [])

    base_output = tmp_path / "output"
    base_output.mkdir()

    state = pipeline.run_pipeline(
        questions=["q"],
        settings=Settings(output_dir=str(base_output)),
    )

    assert state.output_dir == str(base_output)


def test_resume_preserves_existing_metrics(tmp_path: Path, monkeypatch) -> None:
    """When resuming, existing metrics.json is loaded and extended instead of replaced."""
    monkeypatch.setattr(pipeline, "STAGE_ORDER", [])

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    state_path = output_dir / "state.json"

    pre_pause_state = PipelineState(
        questions=["q"],
        current_stage="start",
        output_dir=str(output_dir),
        created_at="2026-04-20T10:00:00Z",
        updated_at="2026-04-20T10:05:00Z",
    )
    pre_pause_state.save(state_path)

    pre_pause_metrics = RunMetrics(
        run_id="run-test123",
        started_at="2026-04-20T10:00:00Z",
        stages=[
            StageMetrics(
                name="query_gen",
                started_at="2026-04-20T10:00:00Z",
                completed_at="2026-04-20T10:01:00Z",
                duration_seconds=5.0,
            ),
        ],
    )
    (output_dir / "metrics.json").write_text(
        pre_pause_metrics.model_dump_json(indent=2), encoding="utf-8"
    )

    pipeline.run_pipeline(
        questions=[],
        settings=Settings(output_dir=str(output_dir)),
        resume_path=state_path,
    )

    metrics_data = (output_dir / "metrics.json").read_text(encoding="utf-8")
    metrics = RunMetrics.model_validate_json(metrics_data)

    assert metrics.run_id == "run-test123"
    assert len(metrics.stages) == 1
    assert metrics.stages[0].name == "query_gen"


def test_resume_creates_new_metrics_when_none_exist(tmp_path: Path, monkeypatch) -> None:
    """When resuming without existing metrics, a fresh RunMetrics is created."""
    monkeypatch.setattr(pipeline, "STAGE_ORDER", [])

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    state_path = output_dir / "state.json"

    state = PipelineState(
        questions=["q"],
        current_stage="start",
        output_dir=str(output_dir),
        created_at="2026-04-20T10:00:00Z",
        updated_at="2026-04-20T10:05:00Z",
    )
    state.save(state_path)

    pipeline.run_pipeline(
        questions=[],
        settings=Settings(output_dir=str(output_dir)),
        resume_path=state_path,
    )

    assert (output_dir / "metrics.json").exists()
    metrics = RunMetrics.model_validate_json(
        (output_dir / "metrics.json").read_text(encoding="utf-8")
    )
    assert metrics.run_id.startswith("run-")

from pathlib import Path

from litresearch import pipeline
from litresearch.config import Settings


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

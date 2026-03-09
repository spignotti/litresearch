"""CLI entrypoints for litresearch."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from litresearch import __version__
from litresearch.config import Settings
from litresearch.pipeline import run_pipeline

app = typer.Typer(help="Automated literature research workflow CLI.")
console = Console()


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(__version__)


@app.command()
def config() -> None:
    """Show basic configuration status without exposing secrets."""
    settings = Settings()
    console.print(f"default_model={settings.default_model}")
    console.print(f"s2_api_key_configured={bool(settings.s2_api_key)}")
    console.print(f"llm_api_key_configured={settings.has_llm_api_key}")


@app.command()
def run(
    questions: Annotated[list[str], typer.Argument(help="One or more research questions.")],
    model: Annotated[str | None, typer.Option(help="Override the default LLM model.")] = None,
    top_n: Annotated[int | None, typer.Option(help="Override the final top-N cutoff.")] = None,
    output_dir: Annotated[str | None, typer.Option(help="Override the output directory.")] = None,
    threshold: Annotated[
        int | None,
        typer.Option("--threshold", help="Override the screening threshold."),
    ] = None,
) -> None:
    """Run the literature research pipeline."""
    settings = Settings()
    if model is not None:
        settings.default_model = model
    if top_n is not None:
        settings.top_n = top_n
    if output_dir is not None:
        settings.output_dir = output_dir
    if threshold is not None:
        settings.screening_threshold = threshold

    state = run_pipeline(questions, settings)
    console.print(f"[green]Run complete.[/green] Output: {state.output_dir}")


@app.command()
def resume(
    state_file: Annotated[str, typer.Argument(help="Path to a saved state.json file.")],
    model: Annotated[str | None, typer.Option(help="Override the default LLM model.")] = None,
    top_n: Annotated[int | None, typer.Option(help="Override the final top-N cutoff.")] = None,
    output_dir: Annotated[str | None, typer.Option(help="Override the output directory.")] = None,
    threshold: Annotated[
        int | None,
        typer.Option("--threshold", help="Override the screening threshold."),
    ] = None,
) -> None:
    """Resume the literature research pipeline from saved state."""
    settings = Settings()
    if model is not None:
        settings.default_model = model
    if top_n is not None:
        settings.top_n = top_n
    if output_dir is not None:
        settings.output_dir = output_dir
    if threshold is not None:
        settings.screening_threshold = threshold

    state = run_pipeline([], settings, resume_path=Path(state_file))
    console.print(f"[green]Resume complete.[/green] Output: {state.output_dir}")


def main() -> None:
    """Run the Typer application."""
    app()

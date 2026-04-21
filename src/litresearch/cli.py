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


def _build_settings(
    *,
    model: str | None = None,
    top_n: int | None = None,
    output_dir: str | None = None,
    threshold: int | None = None,
    inject_pdf_dir: str | None = None,
) -> Settings:
    """Load settings and apply CLI overrides."""
    overrides = {
        key: value
        for key, value in {
            "default_model": model,
            "top_n": top_n,
            "output_dir": output_dir,
            "screening_threshold": threshold,
            "inject_pdf_dir": inject_pdf_dir,
        }.items()
        if value is not None
    }
    return Settings(**overrides)


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(__version__)


@app.command()
def config() -> None:
    """Show basic configuration status without exposing secrets."""
    settings = Settings()
    console.print(f"default_model={settings.default_model}")
    console.print(f"screening_threshold={settings.screening_threshold}")
    console.print(f"top_n={settings.top_n}")
    console.print(f"max_results_per_query={settings.max_results_per_query}")
    console.print(f"pdf_first_pages={settings.pdf_first_pages}")
    console.print(f"pdf_last_pages={settings.pdf_last_pages}")
    console.print(f"inject_pdf_dir={settings.inject_pdf_dir}")
    console.print(f"output_dir={settings.output_dir}")
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
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Overwrite existing output directory."),
    ] = False,
    inject_pdfs: Annotated[
        Path | None,
        typer.Option(
            "--inject-pdfs", help="Directory containing PDFs to inject by paper_id or DOI"
        ),
    ] = None,
    stop_after_screening: Annotated[
        bool,
        typer.Option(
            "--stop-after-screening",
            help="Stop after screening to review papers needing PDFs before analysis",
        ),
    ] = False,
) -> None:
    """Run the literature research pipeline."""
    settings = _build_settings(
        model=model,
        top_n=top_n,
        output_dir=output_dir,
        threshold=threshold,
        inject_pdf_dir=str(inject_pdfs) if inject_pdfs is not None else None,
    )

    state = run_pipeline(
        questions,
        settings,
        overwrite=overwrite,
        inject_pdfs_dir=inject_pdfs,
        stop_after_screening=stop_after_screening,
    )
    if state.screened_papers_completed and not state.analyses:
        console.print(
            f"[yellow]Pipeline paused at screening checkpoint.[/yellow] Output: {state.output_dir}"
        )
    else:
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
    inject_pdfs: Annotated[
        Path | None,
        typer.Option(
            "--inject-pdfs", help="Directory containing PDFs to inject by paper_id or DOI"
        ),
    ] = None,
) -> None:
    """Resume the literature research pipeline from saved state."""
    settings = _build_settings(
        model=model,
        top_n=top_n,
        output_dir=output_dir,
        threshold=threshold,
        inject_pdf_dir=str(inject_pdfs) if inject_pdfs is not None else None,
    )

    state = run_pipeline([], settings, resume_path=Path(state_file), inject_pdfs_dir=inject_pdfs)
    console.print(f"[green]Resume complete.[/green] Output: {state.output_dir}")


def main() -> None:
    """Run the Typer application."""
    app()

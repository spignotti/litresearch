"""CLI entrypoints for litresearch."""

import typer
from rich.console import Console

from litresearch import __version__
from litresearch.config import Settings

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


def main() -> None:
    """Run the Typer application."""
    app()

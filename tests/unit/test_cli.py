import re

from typer.testing import CliRunner

from litresearch.cli import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_run_help_shows_expected_options() -> None:
    result = runner.invoke(app, ["run", "--help"])
    output = _strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "One or more research questions" in output
    assert "default LLM model" in output
    assert "final top-N cutoff" in output
    assert "output directory" in output
    assert "screening threshold" in output
    assert "Overwrite existing output directory" in output


def test_resume_help_shows_expected_options() -> None:
    result = runner.invoke(app, ["resume", "--help"])
    output = _strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "Path to a saved state.json file" in output
    assert "default LLM model" in output
    assert "final top-N cutoff" in output
    assert "output directory" in output
    assert "screening threshold" in output

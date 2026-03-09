from typer.testing import CliRunner

from litresearch.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_run_help_shows_expected_options() -> None:
    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "One or more research questions" in result.stdout
    assert "--model" in result.stdout
    assert "--top-n" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--threshold" in result.stdout


def test_resume_help_shows_expected_options() -> None:
    result = runner.invoke(app, ["resume", "--help"])

    assert result.exit_code == 0
    assert "Path to a saved state.json file" in result.stdout
    assert "--model" in result.stdout
    assert "--top-n" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--threshold" in result.stdout

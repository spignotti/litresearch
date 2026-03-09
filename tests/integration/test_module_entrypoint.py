import subprocess
import sys


def test_module_entrypoint_shows_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "litresearch", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Automated literature research workflow CLI" in result.stdout

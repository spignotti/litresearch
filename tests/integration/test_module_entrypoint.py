import os
import subprocess
import sys
from pathlib import Path


def test_module_entrypoint_shows_help() -> None:
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[2] / "src")
    env["PYTHONPATH"] = src_path if not env.get("PYTHONPATH") else f"{src_path}:{env['PYTHONPATH']}"

    result = subprocess.run(
        [sys.executable, "-m", "litresearch", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert "Automated literature research workflow CLI" in result.stdout

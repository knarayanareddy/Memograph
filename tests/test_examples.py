from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_quickstart_example_runs_offline():
    result = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "quickstart.py")],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "remembered: True" in result.stdout
    assert "recalled topics: ['project_stack']" in result.stdout
    assert "temporary store cleaned up" in result.stdout
